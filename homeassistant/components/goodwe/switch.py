"""GoodWe PV inverter switch settings entities."""

from dataclasses import dataclass
import logging
from typing import Any, override

from goodwe import Inverter, InverterError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GoodweConfigEntry

_LOGGER = logging.getLogger(__name__)

# Settings are read one by one over the single inverter connection
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class GoodweSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Goodwe switch entities."""

    setting: str


SWITCHES = (
    # Charge the battery immediately until the fast charging SoC is reached.
    # Polled, as the inverter may change it on its own (e.g. from the app).
    GoodweSwitchEntityDescription(
        key="fast_charging",
        translation_key="fast_charging",
        entity_category=EntityCategory.CONFIG,
        setting="fast_charging",
    ),
)


def _has_setting(inverter: Inverter, setting: str) -> bool:
    """Return whether the inverter advertises an inverter setting."""
    return any(s.id_ == setting for s in inverter.settings())


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
        if not _has_setting(inverter, description.setting):
            continue
        try:
            current_value = await inverter.read_setting(description.setting)
        except InverterError, ValueError:
            # Inverter model does not support this setting
            _LOGGER.debug("Could not read inverter setting %s", description.setting)
            continue
        if current_value is None:
            # Inverter rejected reading this setting
            _LOGGER.debug("No value for inverter setting %s", description.setting)
            continue

        entities.append(
            InverterSwitchEntity(device_info, description, inverter, current_value)
        )

    async_add_entities(entities)


class InverterSwitchEntity(SwitchEntity):
    """Inverter on/off setting entity."""

    _attr_has_entity_name = True
    entity_description: GoodweSwitchEntityDescription

    def __init__(
        self,
        device_info: DeviceInfo,
        description: GoodweSwitchEntityDescription,
        inverter: Inverter,
        current_value: int,
    ) -> None:
        """Initialize the inverter switch setting entity."""
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{inverter.serial_number}"
        self._attr_device_info = device_info
        self._attr_is_on = bool(current_value)
        self._inverter: Inverter = inverter

    async def async_update(self) -> None:
        """Get the current value from inverter."""
        try:
            value = await self._inverter.read_setting(self.entity_description.setting)
        except InverterError:
            self._attr_available = False
            return
        self._attr_available = value is not None
        if value is not None:
            self._attr_is_on = bool(value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._inverter.write_setting(self.entity_description.setting, 1)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._inverter.write_setting(self.entity_description.setting, 0)
        self._attr_is_on = False
        self.async_write_ha_state()
