"""GoodWe PV inverter selection settings entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from goodwe import Inverter, InverterError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, KEY_DEVICE_INFO, KEY_INVERTER

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GoodweButtonEntityDescription(ButtonEntityDescription):
    """Class describing Goodwe button entities."""

    action: Callable[[Inverter], Awaitable[None]]


SYNCHRONIZE_CLOCK = GoodweButtonEntityDescription(
    key="synchronize_clock",
    translation_key="synchronize_clock",
    entity_category=EntityCategory.CONFIG,
    action=lambda inv: inv.write_setting("time", datetime.now()),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the inverter button entities from a config entry."""
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
            [GoodweButtonEntity(device_info, SYNCHRONIZE_CLOCK, inverter)]
        )


class GoodweButtonEntity(ButtonEntity):
    """Entity representing the inverter clock synchronization button."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: GoodweButtonEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: GoodweButtonEntityDescription,
        inverter: Inverter,
    ) -> None:
        """Initialize the inverter operation mode setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._inverter: Inverter = inverter

    async def async_press(self) -> None:
        """Triggers the button press service."""
        await self.entity_description.action(self._inverter)
