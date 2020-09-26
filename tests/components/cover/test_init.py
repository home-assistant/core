"""The tests for Cover."""
import homeassistant.components.cover as cover


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomCover(cover.CoverDevice):
        pass

    CustomCover()
    assert "CoverDevice is deprecated, modify CustomCover" in caplog.text
