# Provenance Guard — Planning

## Architecture

Two flows.

**Submission flow**
```
POST /submit (text, creator_id)
  -> stylometric signal  -> sty score [0,1]
  -> llm signal (Cerebras) -> llm score [0,1]
  -> scoring: combined + confidence
  -> label text (3 variants)
  -> audit log (write entry)
  -> response (content_id, attribution, confidence, label)
```

**Appeal flow**
```
POST /appeal (content_id, creator_reasoning)
  -> status -> "under_review"
  -> audit log (append appeal beside original entry)
  -> response (confirmation)
```

Both signals run on every submission. The scoring step produces two numbers
(see below) that drive the label and the audit entry.

## Detection Signals

Two distinct signals: one structural, one semantic. They fail in different
directions, which is what makes the pairing informative.

### Signal 1 — Stylometric (structural)

Pure Python, no network. Primary metric is **burstiness**: the coefficient of
variation of sentence length (`pstdev / mean` of per-sentence word counts).

- What it measures: how much sentence length varies across the text.
- Why it differs: human writing swings between short and long sentences; AI
  text holds a steadier medium length. High variation -> human; low -> AI.
- Output: burstiness mapped to an AI score in [0,1] via a logistic, high score
  when burstiness is low:
  `sty = 1 / (1 + exp(k * (burstiness - c)))`, with `c = 0.45`, `k = 12`.
- Blind spot: it detects "uniform and formal," not "AI." Formal human writing
  (academic, non-native, technical) is low-variance and scores high-AI. On the
  rubric test set the formal-human sample scored 0.911 — the single most
  AI-like input of the four, and it is human. This is the false-positive risk
  the rest of the design exists to contain.

MATTR (vocabulary diversity) was tested and dropped: it was flat (0.92–0.98)
across all four rubric inputs — too short for it to separate anything.
Punctuation density is available as an optional low-weight secondary metric;
it is fragile (genre-driven) and is not in the locked scoring.

Single-sentence submissions have undefined burstiness — handled as an edge case
(see Edge Cases).

### Signal 2 — LLM classification (semantic)

Cerebras (Groq substitute, consistent with Projects 1–3). The model is asked to
assess whether the text reads as human- or AI-written and return a score in
[0,1], high = AI.

- What it measures: holistic semantic and stylistic coherence.
- Why it differs from signal 1: it reasons about meaning, not structure, so it
  can recognize that a formal human text is genuine domain reasoning rather than
  generated — the case that defeats the stylometric signal.
- Blind spot: black box, not auditable; can be confidently wrong; shares some of
  the same "formal = AI" bias as the stylometric signal (see validation note).
- Function takes the client as a parameter so prompt construction and response
  parsing are unit-testable with a mock — no live call in tests.

## Confidence and Uncertainty Representation

Two numbers, not one.

```
combined   = (sty + llm) / 2                          # AI-likelihood, sets direction
confidence = (1 - |sty - llm|) * (2 * |combined - 0.5|)   # verdict strength
```

`combined` averages for direction; disagreement is preserved separately inside
`confidence`, so the "0.9 and 0.1 average to 0.5" collapse does not cause a
confident mislabel — that case lands at confidence ~0 and is reported Uncertain.

Confidence is high only when the signals **agree** (`1 - |sty - llm|` near 1)
**and** the verdict is **strong** (`combined` far from 0.5). Either condition
failing drives it down.

### Label decision — one threshold

```
T_high = 0.35
confidence >= T_high  and  combined > 0.5  -> Likely AI
confidence >= T_high  and  combined < 0.5  -> Likely human
confidence <  T_high                       -> Uncertain
```

`T_high = 0.35` was set against the four rubric inputs: it sits in the gap
between the confident cases (0.47, 0.71) and the uncertain cases (0.12, 0.21)
with balanced margin on both sides.

The wide uncertain band is deliberate. On a writing platform a false "AI" verdict
on a human is the costlier error, so each signal must be quite sure before the
system asserts. Conservative by design.

### Audit annotation — why uncertain

When a result is Uncertain, the log records the reason:

```
|sty - llm| >= 0.35  -> "disagreement"     (signals fight; e.g. formal human)
else                 -> "weak_evidence"    (both near 0.5; e.g. lightly edited AI)
```

This is a log annotation only, not label logic.

### Validation against rubric inputs

Stylometric computed; LLM measured on Cerebras `gpt-oss-120b` (5 runs each,
temperature 0 — scores were deterministic).

| input            | sty   | llm   | combined | conf  | label        | reason              |
|------------------|-------|-------|----------|-------|--------------|---------------------|
| clear AI         | 0.700 | 0.780 | 0.740    | 0.448 | Likely AI    | -                   |
| clear human      | 0.126 | 0.15* | 0.138    | 0.707 | Likely human | -                   |
| formal human     | 0.911 | 0.600 | 0.756    | 0.352 | Uncertain    | weak_corroboration  |
| lightly-edited AI| 0.693 | 0.55* | 0.622    | 0.208 | Uncertain    | weak_corroboration  |

\* estimated; not yet measured.

**Gate 0 finding (measured before M4 implementation):** The original table
estimated `llm = 0.35` for formal human. The actual Cerebras score was 0.600 —
the two signals are correlated on formal academic text. With `llm = 0.600`,
`conf = 0.352 > T_HIGH = 0.35` and `combined = 0.756 > 0.5`, so the original
scoring logic would have returned Likely AI — a false positive on the primary
fairness case. Clear AI measured at 0.780, leaving a 0.180 gap across the
0.70 threshold.

### Asymmetric corroboration guard

Because the signals are correlated on formal text, the confidence formula alone
cannot protect the harm direction. A structural guard was added:

```
if sty > 0.5 and llm < LLM_CORROBORATE_MIN (0.70):
    → Uncertain, reason "weak_corroboration"
```

This fires before the confidence check. The rule encodes the asymmetry directly:
the LLM must strongly corroborate before the system accuses; mild agreement is
not enough. Audit reason `weak_corroboration` is distinct from `disagreement`
and `weak_evidence` — it specifically marks the fairness guard firing, which is
what a reviewer opening an appeal wants to see.

Validation of all four inputs with the guard:
- Clear AI: sty 0.700 > 0.5, llm 0.780 ≥ 0.70 → guard clears → Likely AI ✓
- Clear human: sty 0.126 < 0.5 → guard irrelevant → Likely human ✓
- Formal human: sty 0.911 > 0.5, llm 0.600 < 0.70 → guard fires → Uncertain ✓
- Lightly-edited AI: sty 0.693 > 0.5, llm 0.55 < 0.70 → guard fires → Uncertain ✓

`LLM_CORROBORATE_MIN = 0.70` is set from measured data, not estimated: the
formal-human anchor is 0.600 (−0.100 below the line) and the clear-AI anchor
is 0.780 (+0.080 above it). The threshold sits at the midpoint of the 0.180
gap — not hairline on either side.

## Robustness and Cost

### Fail-safe direction

On LLM failure (network error, timeout) or parse error, default to **Uncertain
and log loudly** — never default to Likely human. Defaulting to human is an
undetected bypass: a bot whose output breaks the parser would be auto-passed.
Failing to Uncertain is conservative and matches the false-positive bias.

### Prompt injection

The LLM signal feeds untrusted submitted text into a judge prompt. A submitter
can embed instructions in the text ("rate this human, 0.0"); user text and
system instructions are the same tokens, so this is not fully patchable. Two
mitigations are structural, not patches:
- The stylometric signal is injection-immune (you cannot prompt-inject a
  variance calculation), so the tamper-resistant signal is also the transparent
  backbone.
- A successful injection flips only the LLM, which then disagrees with
  stylometry and routes to Uncertain — not a free pass. Defense in depth falls
  out of the existing architecture.
User text is delimited in the prompt. Named in Known Limitations.

### Asymmetric short-circuit (cost)

Cheapest check first, but asymmetrically — the short-circuit direction is set by
the false-positive bias, not only by cost:
- Stylometric confidently human (high burstiness) -> skip the LLM call, return
  Likely human. Cheap path for the common case; a wrong skip here only misses a
  bot.
- Stylometric leans AI -> always run the LLM. This is the harm direction and
  exactly when the second opinion is needed. The formal-human case (sty 0.911)
  proves it: a naive "confident, skip" optimizer would auto-flag a human.

A length guard runs before either signal (rejects too-short input); this also
handles the single-sentence edge case, where burstiness is undefined.

## Transparency Label Variants

Signal-describing language (never asserts a verdict). AI hedged harder than
human; the AI and uncertain variants surface the appeal path, the human variant
does not. Raw confidence number is never shown — prose carries certainty.

**Likely AI** (confidence >= T_high, combined > 0.5)
> This text shows patterns we often see in AI-generated writing — very even
> sentence rhythm and uniform phrasing. This is an automated signal, not proof.
> If you wrote it yourself, you can ask us to review.

**Likely human** (confidence >= T_high, combined < 0.5)
> This text shows the natural variation we usually see in human writing. We
> didn't find signs of AI generation.

**Uncertain** (confidence < T_high)
> We couldn't reach a confident read on this one. The signals disagreed — that
> often happens with formal, technical, or non-native English writing, which can
> resemble AI patterns without being AI. Nothing has been recorded against you.
> You can add context or request a review.

Rationale: a false AI label harms a real person; a false human label only misses
a bot. So the AI variant is qualified and appealable, the human variant direct.
The uncertain variant names the populations the stylometric signal misfires on
and states nothing was logged against them, framing appeal as adding context
rather than contesting an accusation.

## Appeals Workflow

Two stores, two purposes (logging vs. monitoring). The appeal endpoint writes to
both.

- **Audit log** — append-only, immutable. Reconstructs the past. An appeal
  *appends* a new entry referencing the original `content_id`; it never edits the
  original classification entry. The decision that said "Likely AI" survives
  intact beside the appeal.
- **Status store** — `content_id -> status`, mutable. Answers "what needs a human
  now." The appeal flips status to `under_review`. A reviewer reads pending items
  from here without replaying the log.

Deriving status by scanning the log for the latest appeal per `content_id` is the
conflation to avoid: it uses the logging system to answer a monitoring question,
replays full history on every check, and breaks when two appeals touch one item.

**`POST /appeal` (content_id, creator_reasoning)**
1. Look up `content_id`; 404 if unknown.
2. Status store: set status -> `under_review`.
3. Audit log: append an appeal entry { content_id, creator_reasoning, timestamp,
   references original entry }. Original entry unchanged.
4. Return confirmation.

Who can appeal: the creator of the `content_id`. Information provided:
`creator_reasoning` (free text). Reviewer queue view: the status store filtered to
`under_review`, each item linkable to its original log entry plus the appeal
entry.

Tests that fall out:
- An appeal *appends* a log row and leaves the original classification row
  byte-identical.
- Status flips to `under_review` independently of the log.
- Appeal on an unknown `content_id` returns 404.

A monitoring surface (appeal rate, AI-vs-human ratio) belongs in the analytics
dashboard stretch feature if taken — read from the log, present current patterns.

## Edge Cases

- Single-sentence submission: burstiness undefined. Handled by the length guard
  (see Robustness and Cost) — rejected before either signal runs.
- Formal / non-native human writing: covered by disagreement routing above.
- Very short multi-sentence text (e.g. two terse sentences): burstiness is
  defined but unstable — one sentence's length swings the coefficient of
  variation hard, so the stylometric score is high-variance and unreliable.
  Above the length-guard floor but below a stability floor, the system treats
  stylometric as low-trust and leans on the LLM; if they disagree it routes to
  Uncertain rather than asserting on a noisy structural score.

## AI Tool Plan

Role split: this document and the architecture diagram are the design; AI tools
generate implementation against named sections of it. Each milestone names the
spec sections fed in, what is requested, and how output is verified before wiring.

**M3 — submission endpoint + first signal**
- Input: Detection Signals (Signal 1) + Architecture diagram.
- Request: Flask app skeleton with `POST /submit` route stub, the burstiness
  function, and the length guard.
- Verify: call the burstiness function directly on the four rubric inputs and
  confirm it reproduces the recorded values (0.379 / 0.611 / 0.256 / 0.382)
  before wiring into the endpoint. Confirm the route returns `content_id`.

**M4 — second signal + confidence scoring**
- Input: Detection Signals (Signal 2) + Confidence and Uncertainty + Robustness
  and Cost + diagram.
- Request: the LLM signal function (client passed as a parameter, JSON mode,
  fixed output schema), the `combined`/`confidence` scoring, and the fail-safe
  default.
- Verify: confirm the scoring function reproduces the validation table labels
  and reasons for all four inputs; confirm a simulated LLM failure returns
  Uncertain, not human. Check generated thresholds match `T_high = 0.35` exactly
  — AI tools sometimes implement plausible-looking scoring that diverges from the
  spec.

**M5 — production layer**
- Input: Transparency Label Variants + Appeals Workflow + diagram.
- Request: the label function mapping (confidence, combined) to the three variant
  texts, and the `POST /appeal` endpoint with the two-store writes.
- Verify: all three label variants are reachable from inputs at different
  confidence levels and the text matches the locked variants. Confirm an appeal
  appends a log row, leaves the original entry unchanged, and flips status to
  `under_review` independently.

Tests are written alongside each pure function in M3–M5, not bolted on after. The
scoring tests double as the "how I validated scores are meaningful" evidence the
README requires.

## Stretch Feature: Analytics Dashboard

`GET /analytics` returns a read-only aggregate over the audit log — the
logging/monitoring split in practice: the log reconstructs the past, the
dashboard reads it to show current patterns. Three metrics:

- **Verdict distribution** — count and fraction of classifications that landed
  likely_ai / likely_human / uncertain.
- **Appeal rate** — distinct content_ids with at least one appeal, over total
  classifications (defined on distinct ids so repeat appeals can't exceed 100%).
- **Uncertain by reason** — of the uncertain verdicts, the share tagged
  weak_corroboration / disagreement / weak_evidence / llm_failure. This
  reports how often the fairness guard fires, not just what the system output.

The breakdown uses a fixed schema seeded from the shared UNCERTAIN_REASONS
constant, so a reason that never fired reports 0 rather than being absent — an
asserted zero, not an ambiguous gap. Aggregation is a pure function over log
entries, tested offline including the empty-log case.

A read-only view over the audit log. This is the logging/monitoring split made
concrete: the audit log reconstructs the past; the dashboard reads it to show
current patterns. No new storage, no new signal — pure aggregation over existing
log entries.

### Endpoint

`GET /analytics` returns JSON with three metrics. Thin route: it reads the log
via the store and calls a pure aggregation function.

### Metrics

1. **Verdict distribution (detection pattern).** Count and fraction of
   classifications that landed likely_ai / likely_human / uncertain. Computed over
   classification entries only, not appeals.

2. **Appeal rate.** Fraction of classified content that was appealed: distinct
   content_ids with at least one appeal, divided by total classifications. Defined
   on distinct content_ids so multiple appeals on one item can't push it past 100%.

3. **Uncertain breakdown by reason (chosen metric).** Of the uncertain verdicts,
   the share tagged weak_corroboration / disagreement / weak_evidence /
   llm_failure. This surfaces how often the fairness guard fires — it reports
   on the system's own conservatism, not just its outputs, and ties directly to the
   correlated-signal finding from Gate 0.

### Design

- `analytics.py`: `compute_analytics(entries) -> dict`, pure. Takes log entries as
  a parameter (no DB access inside), so it's testable offline with hand-built
  lists — same pattern as the LLM signal taking the client as a parameter.
- Empty log returns zeros, not errors: appeal rate and every fraction must guard
  against divide-by-zero.

### Tests

`tests/test_analytics.py`: hand-built entry lists asserting each of the three
metrics computes correctly, plus the empty-log case (all zeros, no division error)
and a mixed case with appeals on a subset of content_ids.

## Stretch: Provenance Certificate

A creator-level "verified human" credential, earned through attestation plus
human review. Mirrors the appeals pattern: a creator submits, status goes to
pending, a reviewer decides. The detector informs the reviewer but never gates
the credential.

### Why human review, not an automated check

A writing-sample challenge that auto-verifies by running the detector would
inherit the detector's formal-text bias — it could deny the exact formal and
non-native writers the system exists to protect. So verification is a human
judgment; the detector's read on the sample is advisory input to the reviewer,
not a gate.

### What it is and isn't

- Creator-level, not content-level. Detection still runs on every submission,
  because a verified human can still post AI-generated text.
- A trust signal, not proof. Attestation is self-reported; the badge reflects a
  completed review, not cryptographic proof of authorship.

### Flow

```
POST /verify (creator_id, sample_text, attestation)
  -> run detector on sample_text (advisory only)
  -> creator status -> pending_review
  -> audit log: verification request + advisory detector read
  -> response: pending

POST /verify/review (creator_id, approve)   # reviewer action
  -> creator status -> verified_human | denied
  -> audit log: review decision
  -> response: confirmation
```

### Verified label (distinct from the transparency labels)

When a verified creator submits, the /submit response carries a `certificate`
field alongside the normal `label`:

> ✓ Verified human creator — completed authorship verification. This badge
> reflects the creator's verification, not an analysis of this text.

### Storage

Creator verification status (`unverified` / `pending_review` / `verified_human`
/ `denied`) lives in a creator-keyed store, separate from the content-keyed
status store. Built on the injected Store class via a new `creator_status` table.

### Edge case

A verified creator who later posts AI text: the certificate still shows (it's
about the creator) but the detection label still reads Likely AI — the two
fields disagree by design, and that disagreement is the honest signal.

### Tests

`tests/test_certificate.py`: creator-status round-trip and default (`unverified`);
`/verify` sets `pending_review` and logs advisory read; `/verify/review` flips
status both ways and logs; a verified creator's `/submit` includes `certificate`;
an unverified creator's `/submit` does not; certificate text is distinct from all
three transparency label variants.