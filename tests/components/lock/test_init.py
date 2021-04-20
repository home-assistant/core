"""The tests for Lock."""
from homeassistant.components import lock


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomLock(lock.LockDevice):
        pass

    CustomLock()
    assert "LockDevice is deprecated, modify CustomLock" in caplog.text
