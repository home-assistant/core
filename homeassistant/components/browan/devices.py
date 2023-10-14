"""Import Browan devices and add supported sensor types."""
from pyliblorawan.devices.browan.tbms100 import TBMS100

from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_TEMPERATURE


class HassTBMS100(TBMS100):
    """Import TBMS100 device."""

    @staticmethod
    def supported_sensors() -> list:
        """Return supported measurements keys for this sensor."""
        return [ATTR_BATTERY_LEVEL, ATTR_TEMPERATURE]
