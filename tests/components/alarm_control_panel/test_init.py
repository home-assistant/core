"""Tests for Alarm control panel."""
from homeassistant.components import alarm_control_panel


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomAlarm(alarm_control_panel.AlarmControlPanel):
        def supported_features(self):
            pass

    CustomAlarm()
    assert "AlarmControlPanel is deprecated, modify CustomAlarm" in caplog.text
