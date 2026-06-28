# Stylometric mapping (logistic burstiness -> AI score)
BURSTINESS_CENTER = 0.45
BURSTINESS_STEEPNESS = 12

# Length guard
MIN_SENTENCES = 2          # burstiness undefined below this
MIN_WORDS = 15             # reject trivially short input (400)

# Scoring
T_HIGH = 0.35              # confidence >= -> confident verdict; below -> Uncertain
DISAGREE = 0.35            # |sty - llm| >= this -> "disagreement" audit reason
LLM_CORROBORATE_MIN = 0.70 # LLM must reach this to confirm a stylometric AI accusation

# Cost optimization
SHORT_CIRCUIT_ENABLED = True
STY_HUMAN_SKIP = 0.15      # stylometric <= this -> confidently human, skip LLM

# Uncertain audit reasons — single source of truth for scoring, pipeline, and analytics
REASON_WEAK_CORROBORATION = "weak_corroboration"
REASON_DISAGREEMENT = "disagreement"
REASON_WEAK_EVIDENCE = "weak_evidence"
REASON_LLM_FAILURE = "llm_failure"
UNCERTAIN_REASONS = (
    REASON_WEAK_CORROBORATION,
    REASON_DISAGREEMENT,
    REASON_WEAK_EVIDENCE,
    REASON_LLM_FAILURE,
)

# Rate limiting
RATE_LIMITS = "10 per minute;100 per day"

# LLM — gpt-oss-120b is a reasoning model; reasoning tokens come first,
# answer goes in content. 2048 comfortably covers reasoning + JSON output.
LLM_MODEL = "gpt-oss-120b"
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 2048
