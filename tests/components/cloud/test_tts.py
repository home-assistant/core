"""Tests for cloud tts."""
from homeassistant.components.cloud import tts


def test_schema():
    """Test schema."""
    assert "nl-NL" in tts.SUPPORT_LANGUAGES

    processed = tts.PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL"})
    assert processed["gender"] == "female"

    # Should not raise
    processed = tts.PLATFORM_SCHEMA(
        {"platform": "cloud", "language": "nl-NL", "gender": "female"}
    )
