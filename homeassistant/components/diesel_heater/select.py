"""Select platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VevorHeaterConfigEntry
from .const import (
    BACKLIGHT_OPTIONS,
    DOMAIN,
    LANGUAGE_OPTIONS,
    PUMP_TYPE_OPTIONS,
    RUNNING_MODE_LEVEL,
    RUNNING_MODE_TEMPERATURE,
    RUNNING_MODE_VENTILATION,
    RUNNING_MODE_NAMES,
    RUNNING_STEP_STANDBY,
    RUNNING_STEP_VENTILATION,
    TANK_VOLUME_OPTIONS,
)
from .coordinator import VevorHeaterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater select from config entry.

    Entities are created conditionally based on the detected BLE protocol.
    Mode 0 (unknown) creates all entities as safe fallback.
    """
    coordinator = entry.runtime_data
    mode = coordinator.protocol_mode

    # Core select entities (all protocols)
    entities: list[SelectEntity] = [
        VevorHeaterModeSelect(coordinator),
    ]

    # Config selects (AA66Encrypted + CBFF: language, pump_type, tank_volume)
    if mode in (0, 4, 6):
        entities.extend([
            VevorHeaterLanguageSelect(coordinator),
            VevorHeaterPumpTypeSelect(coordinator),
            VevorHeaterTankVolumeSelect(coordinator),
        ])

    # Backlight select (encrypted + CBFF protocols)
    if mode in (0, 2, 4, 6):
        entities.append(VevorBacklightSelect(coordinator))

    async_add_entities(entities)


class VevorHeaterModeSelect(SelectEntity):
    """Select entity for Vevor Heater running mode.

    For ABBA/HeaterCC devices, includes a "Ventilation" option when the heater
    is in standby or already ventilating. This allows fan-only operation.
    """

    _attr_has_entity_name = True
    _attr_name = "Running Mode"
    _attr_icon = "mdi:cog"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the select entity."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_running_mode"

    @property
    def options(self) -> list[str]:
        """Return available running mode options.

        For ABBA devices, include Ventilation when heater is in standby or ventilating.
        This follows Xev's suggestion in Issue #30 for dynamic options.
        """
        base_options = [
            RUNNING_MODE_NAMES[RUNNING_MODE_LEVEL],
            RUNNING_MODE_NAMES[RUNNING_MODE_TEMPERATURE],
        ]

        # Add Ventilation option for ABBA devices when in standby or already ventilating
        if self.coordinator.protocol_mode == 5:  # ABBA protocol
            running_step = self.coordinator.data.get("running_step")
            if running_step in (RUNNING_STEP_STANDBY, RUNNING_STEP_VENTILATION):
                base_options.append(RUNNING_MODE_NAMES[RUNNING_MODE_VENTILATION])

        return base_options

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("connected", False)

    @property
    def current_option(self) -> str | None:
        """Return the current running mode."""
        # Check if currently ventilating (ABBA specific)
        running_step = self.coordinator.data.get("running_step")
        if running_step == RUNNING_STEP_VENTILATION:
            return RUNNING_MODE_NAMES[RUNNING_MODE_VENTILATION]

        mode = self.coordinator.data.get("running_mode")
        if mode is not None:
            return RUNNING_MODE_NAMES.get(mode)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the running mode."""
        # Find the mode value for the selected option
        mode_value = None
        for mode, name in RUNNING_MODE_NAMES.items():
            if name == option:
                mode_value = mode
                break

        if mode_value is not None:
            _LOGGER.info("Changing running mode to: %s (value: %d)", option, mode_value)
            await self.coordinator.async_set_mode(mode_value)
        else:
            _LOGGER.error("Unknown running mode: %s", option)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterLanguageSelect(SelectEntity):
    """Select entity for Vevor Heater voice notification language."""

    _attr_has_entity_name = True
    _attr_name = "Language"
    _attr_icon = "mdi:translate"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(LANGUAGE_OPTIONS.values())

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the select entity."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_language"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("connected", False)

    @property
    def current_option(self) -> str | None:
        """Return the current language."""
        language_code = self.coordinator.data.get("language")
        if language_code is not None:
            return LANGUAGE_OPTIONS.get(language_code, f"Unknown ({language_code})")
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the language."""
        # Find the language code for the selected option
        language_code = None
        for code, name in LANGUAGE_OPTIONS.items():
            if name == option:
                language_code = code
                break

        if language_code is not None:
            _LOGGER.info("Changing language to: %s (code: %d)", option, language_code)
            await self.coordinator.async_set_language(language_code)
        else:
            _LOGGER.error("Unknown language: %s", option)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterPumpTypeSelect(SelectEntity):
    """Select entity for Vevor Heater oil pump type."""

    _attr_has_entity_name = True
    _attr_name = "Pump Type"
    _attr_icon = "mdi:pump"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(PUMP_TYPE_OPTIONS.values())

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the select entity."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_pump_type"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Not available if RF433 mode is active (pump_type will be None)
        return (
            self.coordinator.data.get("connected", False)
            and self.coordinator.data.get("pump_type") is not None
        )

    @property
    def current_option(self) -> str | None:
        """Return the current pump type."""
        pump_type = self.coordinator.data.get("pump_type")
        if pump_type is not None:
            return PUMP_TYPE_OPTIONS.get(pump_type, f"Type {pump_type}")
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the pump type."""
        # Find the pump type code for the selected option
        pump_code = None
        for code, name in PUMP_TYPE_OPTIONS.items():
            if name == option:
                pump_code = code
                break

        if pump_code is not None:
            _LOGGER.info("Changing pump type to: %s (code: %d)", option, pump_code)
            await self.coordinator.async_set_pump_type(pump_code)
        else:
            _LOGGER.error("Unknown pump type: %s", option)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHeaterTankVolumeSelect(SelectEntity):
    """Select entity for Vevor Heater tank volume."""

    _attr_has_entity_name = True
    _attr_name = "Tank Volume"
    _attr_icon = "mdi:gas-station"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(TANK_VOLUME_OPTIONS.values())

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the select entity."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_tank_volume_select"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("connected", False)

    @property
    def current_option(self) -> str | None:
        """Return the current tank volume."""
        tank_volume = self.coordinator.data.get("tank_volume")
        if tank_volume is not None:
            # Return exact match or closest option
            if tank_volume in TANK_VOLUME_OPTIONS:
                return TANK_VOLUME_OPTIONS[tank_volume]
            # If not an exact match, show the raw value
            return f"{tank_volume} L"
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the tank volume."""
        # Find the volume value for the selected option
        volume = None
        for vol, name in TANK_VOLUME_OPTIONS.items():
            if name == option:
                volume = vol
                break

        if volume is not None:
            _LOGGER.info("Changing tank volume to: %s (value: %d)", option, volume)
            await self.coordinator.async_set_tank_volume(volume)
        else:
            _LOGGER.error("Unknown tank volume: %s", option)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorBacklightSelect(SelectEntity):
    """Select entity for display backlight brightness (cmd 21).

    Discrete brightness values matching the Vevor app:
    Off, 1-10, 20, 30, ..., 100.
    Replaces the old 0-100 number slider which was hard to use.
    """

    _attr_has_entity_name = True
    _attr_name = "Backlight"
    _attr_icon = "mdi:brightness-6"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(BACKLIGHT_OPTIONS.values())

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the select entity."""
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }
        self._attr_unique_id = f"{coordinator.address}_backlight_select"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("backlight") is not None

    @property
    def current_option(self) -> str | None:
        """Return the current backlight level."""
        backlight = self.coordinator.data.get("backlight")
        if backlight is not None:
            if backlight in BACKLIGHT_OPTIONS:
                return BACKLIGHT_OPTIONS[backlight]
            return str(backlight)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the backlight brightness."""
        for value, name in BACKLIGHT_OPTIONS.items():
            if name == option:
                _LOGGER.info("Setting backlight to: %s (value: %d)", option, value)
                await self.coordinator.async_set_backlight(value)
                return
        _LOGGER.error("Unknown backlight option: %s", option)

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
