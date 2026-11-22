"""Test Tuya cat litter box entity descriptions."""

from homeassistant.components.tuya.button import BUTTONS
from homeassistant.components.tuya.const import DPCode, DeviceCategory
from homeassistant.components.tuya.number import NUMBERS
from homeassistant.components.tuya.switch import SWITCHES


def test_cat_litter_box_controls() -> None:
    """Test cat litter box controls are mapped."""
    assert {description.key for description in BUTTONS[DeviceCategory.MSP]} >= {
        DPCode.FACTORY_RESET,
        DPCode.MANUAL_CLEAN,
        DPCode.START,
    }
    assert {description.key for description in SWITCHES[DeviceCategory.MSP]} >= {
        DPCode.AUTO_CLEAN,
        DPCode.SLEEP,
        DPCode.UV,
    }
    assert {description.key for description in NUMBERS[DeviceCategory.MSP]} >= {
        DPCode.DELAY_CLEAN_TIME,
        DPCode.SLEEP_END_TIME,
        DPCode.SLEEP_START_TIME,
    }
