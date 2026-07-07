"""Support for switch entities."""

from typing import Any, override

from gardena_bluetooth.const import Valve, Valve1, Valve2

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import WATERING_COMMAND_SOURCE
from .coordinator import GardenaBluetoothConfigEntry, GardenaBluetoothCoordinator
from .entity import GardenaBluetoothEntity

FALLBACK_WATERING_TIME_IN_SECONDS = 60 * 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenaBluetoothConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []

    if GardenaBluetoothValveSwitch.characteristics.issubset(
        coordinator.characteristics
    ):
        entities.append(GardenaBluetoothValveSwitch(coordinator))

    entities.extend(
        entity_cls(coordinator)
        for entity_cls in (GardenaBluetoothValve1Switch, GardenaBluetoothValve2Switch)
        if entity_cls.characteristics.issubset(coordinator.characteristics)
    )

    async_add_entities(entities)


class GardenaBluetoothValveSwitch(GardenaBluetoothEntity, SwitchEntity):
    """Switch alias for the old single-valve Bluetooth-only Water Control."""

    characteristics = {
        Valve.state.unique_id,
        Valve.manual_watering_time.unique_id,
        Valve.remaining_open_time.unique_id,
    }

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator, {Valve.state.uuid, Valve.manual_watering_time.uuid}
        )
        self._attr_unique_id = f"{coordinator.address}-{Valve.state.unique_id}"
        self._attr_translation_key = "state"
        self._attr_is_on = None
        self._attr_entity_registry_enabled_default = False

    @override
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self.coordinator.get_cached(Valve.state)
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if not (data := self.coordinator.data.get(Valve.manual_watering_time.uuid)):
            raise HomeAssistantError("Unable to get manual activation time.")

        value = Valve.manual_watering_time.decode(data)
        await self.coordinator.write(Valve.remaining_open_time, value)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.write(Valve.remaining_open_time, 0)
        self._attr_is_on = False
        self.async_write_ha_state()


class GardenaBluetoothValveXSwitch(GardenaBluetoothEntity, SwitchEntity):
    """Base switch alias for the Smart Water Control family (Valve1/Valve2)."""

    # Annotated as the concrete classes: the released library (2.8.1) declares
    # the ValveX base attributes with `=` instead of `:`, which mypy resolves
    # to typing special forms when accessed through type[ValveX].
    _service: type[Valve1 | Valve2]
    characteristics: set[str]

    _attr_is_on: bool | None = None
    _attr_entity_registry_enabled_default = False

    @override
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Derive the required characteristics from the concrete service."""
        super().__init_subclass__(**kwargs)
        cls.characteristics = {
            cls._service.state.unique_id,
            cls._service.manual_watering_duration.unique_id,
            cls._service.available.unique_id,
            cls._service.start_watering.unique_id,
            cls._service.stop_watering.unique_id,
        }

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
    ) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator,
            {
                self._service.state.uuid,
                self._service.manual_watering_duration.uuid,
                self._service.available.uuid,
            },
        )
        self._attr_unique_id = f"{coordinator.address}-{self._service.state.unique_id}"

    @override
    def _handle_coordinator_update(self) -> None:
        self._attr_is_on = self.coordinator.get_cached(self._service.state)
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on for the configured manual watering duration."""
        cached = self.coordinator.get_cached(self._service.manual_watering_duration)
        duration = cached if cached is not None else FALLBACK_WATERING_TIME_IN_SECONDS
        await self.coordinator.write(
            self._service.start_watering,
            {0: WATERING_COMMAND_SOURCE, 1: str(duration)},
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.write(
            self._service.stop_watering,
            {0: WATERING_COMMAND_SOURCE},
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class GardenaBluetoothValve1Switch(GardenaBluetoothValveXSwitch):
    """Valve1 switch (G-19033 wc_single, valve 1 of G-19034 wc_dual)."""

    _service = Valve1
    _attr_translation_key = "state_valve_1"


class GardenaBluetoothValve2Switch(GardenaBluetoothValveXSwitch):
    """Valve2 switch (G-19034 wc_dual second valve)."""

    _service = Valve2
    _attr_translation_key = "state_valve_2"
