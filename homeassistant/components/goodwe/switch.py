"""GoodWe PV inverter switch settings entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, override

from goodwe import Inverter, InverterError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import GoodweConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GoodweSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Goodwe switch entities."""

    getter: Callable[[Inverter], Awaitable[int]]
    setter: Callable[[Inverter, bool], Awaitable[None]]


SWITCHES = (
    # Fast charging of the battery, available on ET/EH and ES/EM families.
    GoodweSwitchEntityDescription(
        key="fast_charging",
        translation_key="fast_charging",
        entity_category=EntityCategory.CONFIG,
        getter=lambda inv: inv.read_setting("fast_charging"),
        setter=lambda inv, value: inv.write_setting("fast_charging", 1 if value else 0),
    ),
    # Backup/UPS power supply, available on ET/EH and ES/EM families.
    GoodweSwitchEntityDescription(
        key="backup_supply",
        translation_key="backup_supply",
        entity_category=EntityCategory.CONFIG,
        getter=lambda inv: inv.read_setting("backup_supply"),
        setter=lambda inv, value: inv.write_setting("backup_supply", 1 if value else 0),
    ),
    # Load control switch, available on ET/EH family only.
    GoodweSwitchEntityDescription(
        key="load_control_switch",
        translation_key="load_control_switch",
        entity_category=EntityCategory.CONFIG,
        getter=lambda inv: inv.read_setting("load_control_switch"),
        setter=lambda inv, value: inv.write_setting(
            "load_control_switch", 1 if value else 0
        ),
    ),
    # Depth-of-discharge holding, available on ET/EH family only.
    GoodweSwitchEntityDescription(
        key="dod_holding",
        translation_key="dod_holding",
        entity_category=EntityCategory.CONFIG,
        getter=lambda inv: inv.read_setting("dod_holding"),
        setter=lambda inv, value: inv.write_setting("dod_holding", 1 if value else 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoodweConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the inverter switch entities from a config entry."""
    inverter = config_entry.runtime_data.inverter
    device_info = config_entry.runtime_data.device_info

    entities = []

    for description in SWITCHES:
        try:
            current_value = await description.getter(inverter)
        except InverterError, ValueError:
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.key)
            continue

        entities.append(
            InverterSwitchEntity(
                device_info, description, inverter, bool(current_value)
            )
        )

    async_add_entities(entities)


class InverterSwitchEntity(SwitchEntity):
    """Inverter on/off setting entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    entity_description: GoodweSwitchEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: GoodweSwitchEntityDescription,
        inverter: Inverter,
        current_value: bool,
    ) -> None:
        """Initialize the switch inverter setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}-{description.key}-{inverter.serial_number}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain
        self._attr_device_info = device_info
        self._attr_is_on = current_value
        self._inverter: Inverter = inverter

    async def async_update(self) -> None:
        """Get the current value from inverter."""
        value = await self.entity_description.getter(self._inverter)
        self._attr_is_on = bool(value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.entity_description.setter(self._inverter, True)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.entity_description.setter(self._inverter, False)
        self._attr_is_on = False
        self.async_write_ha_state()
