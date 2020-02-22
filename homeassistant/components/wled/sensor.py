"""Support for WLED sensors."""
from datetime import timedelta
import logging
from typing import Callable, List, Optional, Union

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_BYTES, DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import utcnow

from . import WLED, WLEDDeviceEntity
from .const import ATTR_LED_COUNT, ATTR_MAX_POWER, CURRENT_MA, DATA_WLED_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up WLED sensor based on a config entry."""
    wled: WLED = hass.data[DOMAIN][entry.entry_id][DATA_WLED_CLIENT]

    sensors = [
        WLEDEstimatedCurrentSensor(entry.entry_id, wled),
        WLEDUptimeSensor(entry.entry_id, wled),
        WLEDFreeHeapSensor(entry.entry_id, wled),
    ]

    async_add_entities(sensors, True)


class WLEDSensor(WLEDDeviceEntity):
    """Defines a WLED sensor."""

    def __init__(
        self,
        entry_id: str,
        wled: WLED,
        name: str,
        icon: str,
        unit_of_measurement: str,
        key: str,
        enabled_default: bool = True,
    ) -> None:
        """Initialize WLED sensor."""
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._key = key

        super().__init__(entry_id, wled, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.wled.device.info.mac_address}_{self._key}"

    @property
    def state(self) -> Union[None, str, int, float]:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class WLEDEstimatedCurrentSensor(WLEDSensor):
    """Defines a WLED estimated current sensor."""

    def __init__(self, entry_id: str, wled: WLED) -> None:
        """Initialize WLED estimated current sensor."""
        super().__init__(
            entry_id,
            wled,
            f"{wled.device.info.name} Estimated Current",
            "mdi:power",
            CURRENT_MA,
            "estimated_current",
        )

    async def _wled_update(self) -> None:
        """Update WLED entity."""
        self._state = self.wled.device.info.leds.power
        self._attributes = {
            ATTR_LED_COUNT: self.wled.device.info.leds.count,
            ATTR_MAX_POWER: self.wled.device.info.leds.max_power,
        }


class WLEDUptimeSensor(WLEDSensor):
    """Defines a WLED uptime sensor."""

    def __init__(self, entry_id: str, wled: WLED) -> None:
        """Initialize WLED uptime sensor."""
        super().__init__(
            entry_id,
            wled,
            f"{wled.device.info.name} Uptime",
            "mdi:clock-outline",
            None,
            "uptime",
            enabled_default=False,
        )

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this sensor."""
        return DEVICE_CLASS_TIMESTAMP

    async def _wled_update(self) -> None:
        """Update WLED uptime sensor."""
        uptime = utcnow() - timedelta(seconds=self.wled.device.info.uptime)
        self._state = uptime.replace(microsecond=0).isoformat()


class WLEDFreeHeapSensor(WLEDSensor):
    """Defines a WLED free heap sensor."""

    def __init__(self, entry_id: str, wled: WLED) -> None:
        """Initialize WLED free heap sensor."""
        super().__init__(
            entry_id,
            wled,
            f"{wled.device.info.name} Free Memory",
            "mdi:memory",
            DATA_BYTES,
            "free_heap",
            enabled_default=False,
        )

    async def _wled_update(self) -> None:
        """Update WLED uptime sensor."""
        self._state = self.wled.device.info.free_heap
