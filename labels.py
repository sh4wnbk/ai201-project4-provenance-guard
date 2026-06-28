"""Pure label text — locked variants from the spec."""

_LABELS: dict[str, str] = {
    "likely_ai": (
        "This text shows patterns we often see in AI-generated writing — very even "
        "sentence rhythm and uniform phrasing. This is an automated signal, not proof. "
        "If you wrote it yourself, you can ask us to review."
    ),
    "likely_human": (
        "This text shows the natural variation we usually see in human writing. "
        "We didn't find signs of AI generation."
    ),
    "uncertain": (
        "We couldn't reach a confident read on this one. The signals disagreed — that "
        "often happens with formal, technical, or non-native English writing, which can "
        "resemble AI patterns without being AI. Nothing has been recorded against you. "
        "You can add context or request a review."
    ),
}


def label_text(label_key: str) -> str:
    """Return the transparency label string for the given key."""
    try:
        return _LABELS[label_key]
    except KeyError:
        raise ValueError(f"Unknown label key: {label_key!r}")
