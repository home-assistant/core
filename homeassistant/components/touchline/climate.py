"""Platform for Roth Touchline floor heating controller."""

from typing import TYPE_CHECKING, Any, NamedTuple, override

from pytouchline_extended import RoomStatus, TouchlineError

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_NONE,
    PRESET_SLEEP,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TouchlineConfigEntry, TouchlineCoordinator

# Actions are serialized by the library's per-controller lock.
PARALLEL_UPDATES = 0


class PresetMode(NamedTuple):
    """Settings for preset mode."""

    mode: int
    program: int


PRESET_MODES = {
    PRESET_NONE: PresetMode(mode=0, program=0),
    PRESET_SLEEP: PresetMode(mode=1, program=0),
    PRESET_AWAY: PresetMode(mode=2, program=0),
    "program_1": PresetMode(mode=0, program=1),
    "program_2": PresetMode(mode=0, program=2),
    "program_3": PresetMode(mode=0, program=3),
}

TOUCHLINE_HA_PRESETS: dict[tuple[int | None, int | None], str] = {
    (settings.mode, settings.program): preset
    for preset, settings in PRESET_MODES.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Touchline devices from a config entry."""
    coordinator = entry.runtime_data
    if TYPE_CHECKING:
        assert entry.unique_id is not None
    controller_device_id = dr.async_get_device_id_by_identifier(
        hass, (DOMAIN, entry.unique_id), config_entry_id=entry.entry_id
    )
    known_room_ids: set[str] = set()

    @callback
    def _async_add_new_thermostats() -> None:
        """Add entities for thermostats paired since the last update."""
        if new_room_ids := coordinator.data.keys() - known_room_ids:
            known_room_ids.update(new_room_ids)
            async_add_entities(
                Touchline(coordinator, room_id, controller_device_id)
                for room_id in new_room_ids
            )

    _async_add_new_thermostats()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_thermostats))


class Touchline(CoordinatorEntity[TouchlineCoordinator], ClimateEntity):
    """Representation of a Touchline device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_preset_modes = list(PRESET_MODES)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "climate"

    def __init__(
        self,
        coordinator: TouchlineCoordinator,
        room_id: str,
        controller_device_id: str,
    ) -> None:
        """Initialize the Touchline device."""
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_unique_id = room_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, room_id)},
            name=self._room.name,
            manufacturer="Roth",
            model="Thermostat",
            via_device_id=controller_device_id,
        )

    @property
    def _room(self) -> RoomStatus:
        """Return the latest state of this thermostat."""
        return self.coordinator.data[self._room_id]

    @property
    @override
    def available(self) -> bool:
        """Return if the thermostat is still reported by the controller."""
        return super().available and self._room_id in self.coordinator.data

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._room.temperature

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._room.target_temperature

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return TOUCHLINE_HA_PRESETS.get(
            (self._room.operation_mode, self._room.week_program)
        )

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        preset = PRESET_MODES[preset_mode]
        controller = self.coordinator.controller
        index = self._room.index
        try:
            success = await controller.set_room_operation_mode_async(
                index, preset.mode
            ) and await controller.set_room_week_program_async(index, preset.program)
        except TouchlineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="error_set_preset"
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="error_set_preset"
            )
        await self.coordinator.async_request_refresh()

    @override
    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode.

        Heat is the only supported mode, so there is nothing to change.
        """

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        try:
            success = (
                await self.coordinator.controller.set_room_target_temperature_async(
                    self._room.index, kwargs[ATTR_TEMPERATURE]
                )
            )
        except TouchlineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="error_set_temperature"
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="error_set_temperature"
            )
        await self.coordinator.async_request_refresh()
