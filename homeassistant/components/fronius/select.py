"""Select entities for the Fronius Modbus controls."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, override

from fronius_modbus import ForcedMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import discovery_signal
from .entity import FroniusEntity, FroniusEntityDescription

if TYPE_CHECKING:
    from . import FroniusConfigEntry
    from .coordinator import (
        FroniusCoordinatorBase,
        FroniusModbusSettingsUpdateCoordinator,
    )

# writes go to one device at a time
PARALLEL_UPDATES: Final = 1


@dataclass(frozen=True, kw_only=True)
class FroniusSelectEntityDescription(FroniusEntityDescription, SelectEntityDescription):
    """Describes a Fronius Modbus select entity."""


# Forcing takes over the rate limit of the opposite direction and leaves the
# one of the forced direction to the user - an active limit there caps the
# forced power. The library sequences the writes so the device never sees
# both rates negative, which it refuses.
MODBUS_SELECT_ENTITY_DESCRIPTIONS: list[FroniusSelectEntityDescription] = [
    FroniusSelectEntityDescription(
        key="battery_forced_mode",
        options=[mode.value for mode in ForcedMode],
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FroniusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fronius select entities based on a config entry."""
    solar_net = config_entry.runtime_data
    for coordinator in solar_net.modbus_settings_coordinators:
        coordinator.add_entities_for_seen_keys(
            async_add_entities, Platform.SELECT, BatteryForcedModeSelect
        )

    @callback
    def async_add_new_entities(coordinator: FroniusCoordinatorBase) -> None:
        """Add the entities of a coordinator found after setup."""
        if Platform.SELECT not in coordinator.valid_descriptions:
            return
        coordinator.add_entities_for_seen_keys(
            async_add_entities, Platform.SELECT, BatteryForcedModeSelect
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, discovery_signal(config_entry.entry_id), async_add_new_entities
        )
    )


class BatteryForcedModeSelect(FroniusEntity, SelectEntity):
    """Force the battery of an inverter to charge or discharge."""

    entity_description: FroniusSelectEntityDescription
    coordinator: FroniusModbusSettingsUpdateCoordinator

    def __init__(
        self,
        coordinator: FroniusModbusSettingsUpdateCoordinator,
        description: FroniusSelectEntityDescription,
        solar_net_id: str,
    ) -> None:
        """Set up the battery forced mode select of an inverter."""
        super().__init__(coordinator, description, solar_net_id)
        self._attr_device_info = coordinator.inverter_info.device_info
        self._attr_unique_id = (
            f"{coordinator.inverter_info.unique_id}-modbus-{description.key}"
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the mode as the device reports it."""
        return self._device_data()[self.response_key]["value"]  # type: ignore[no-any-return]

    @override
    async def async_select_option(self, option: str) -> None:
        """Put the battery into the selected mode."""
        await self.coordinator.async_write_component(
            self.coordinator.modbus_inverter.storage,
            lambda storage: storage.set_forced_mode(ForcedMode(option)),
        )
