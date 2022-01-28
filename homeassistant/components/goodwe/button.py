"""GoodWe PV inverter selection settings entities."""
import logging

from datetime import datetime
from goodwe import Inverter, InverterError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, KEY_DEVICE_INFO, KEY_INVERTER

_LOGGER = logging.getLogger(__name__)


SYNCHRONIZE_CLOCK = ButtonEntityDescription(
    key="synchronize_clock",
    name="Synchronize inverter clock",
    icon="mdi:clock-check-outline",
    entity_category=ENTITY_CATEGORY_CONFIG,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the inverter select entities from a config entry."""
    inverter = hass.data[DOMAIN][config_entry.entry_id][KEY_INVERTER]
    device_info = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE_INFO]

    # read current time from the inverter
    try:
        await inverter.read_setting("time")
    except (InverterError, ValueError):
        # Inverter model does not support clock synchronization
        _LOGGER.debug("Could not read inverter current clock time")
    else:
        async_add_entities(
            [SynchronizeInverterClockEntity(device_info, SYNCHRONIZE_CLOCK, inverter)]
        )


class SynchronizeInverterClockEntity(ButtonEntity):
    """Entity representing the inverter clock synchronization button."""

    _attr_should_poll = False

    def __init__(
        self,
        device_info: DeviceInfo,
        description: ButtonEntityDescription,
        inverter: Inverter,
    ) -> None:
        """Initialize the inverter operation mode setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._inverter: Inverter = inverter

    async def async_press(self) -> None:
        """Send out a persistent notification."""
        await self._inverter.write_setting("time", datetime.now())
