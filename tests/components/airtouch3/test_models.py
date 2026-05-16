"""Test AirTouch 3 data models."""

from homeassistant.components.airtouch3.comms.airtouch_aircon import Aircon
from homeassistant.components.airtouch3.comms.airtouch_zone import AirtouchZone


def test_aircon_desired_temperature() -> None:
    """Test AirTouch AC target temperature accessors."""
    aircon = Aircon(1)

    aircon.desired_temperature = 22

    assert aircon.desired_temperature == 22


def test_zone_touch_pad_temperature() -> None:
    """Test zone touchpad temperature accessors."""
    zone = AirtouchZone(20)

    zone.touch_pad_temperature = 21

    assert zone.touch_pad_temperature == 21
