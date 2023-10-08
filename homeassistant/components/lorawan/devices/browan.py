"""Import Browan devices and add supported sensor types."""
from pyliblorawan.devices.browan.tbms100 import TBMS100

from ..models import SensorTypes


class HassTBMS100(TBMS100):
    """Import TBMS100 device."""

    @staticmethod
    def supported_sensors() -> list:
        """Return supported measurements for this sensor."""
        return [SensorTypes.Temperature, SensorTypes.BatteryLevel]
