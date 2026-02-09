"""Switch platform for Vevor Diesel Heater."""
from __future__ import annotations

PARALLEL_UPDATES = 1

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VevorHeaterConfigEntry
from .const import CONF_EXTERNAL_TEMP_SENSOR, DOMAIN, RUNNING_MODE_TEMPERATURE, RUNNING_STATE_ON
from .coordinator import VevorHeaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VevorHeaterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vevor Heater switch.

    Entities are created conditionally based on the detected BLE protocol.
    Mode 0 (unknown) creates all entities as safe fallback.
    """
    coordinator = entry.runtime_data
    mode = coordinator.protocol_mode

    # Core switches (all protocols)
    entities: list[SwitchEntity] = [
        VevorHeaterPowerSwitch(coordinator),
        VevorAutoOffsetSwitch(coordinator),
    ]

    # Auto Start/Stop (AA66Encrypted, ABBA, CBFF)
    if mode in (0, 4, 5, 6):
        entities.append(VevorAutoStartStopSwitch(coordinator))

    # Unit settings (AA66Encrypted, ABBA, CBFF)
    if mode in (0, 4, 5, 6):
        entities.extend([
            VevorTempUnitSwitch(coordinator),
            VevorAltitudeUnitSwitch(coordinator),
        ])

    # High altitude (ABBA only)
    if mode in (0, 5):
        entities.append(VevorHighAltitudeSwitch(coordinator))

    async_add_entities(entities)


class VevorHeaterPowerSwitch(CoordinatorEntity[VevorHeaterCoordinator], SwitchEntity):
    """Vevor Heater power switch."""

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_power"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def is_on(self) -> bool:
        """Return true if heater is on."""
        return self.coordinator.data.get("running_state") == RUNNING_STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the heater on."""
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the heater off."""
        await self.coordinator.async_turn_off()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorAutoStartStopSwitch(CoordinatorEntity[VevorHeaterCoordinator], SwitchEntity):
    """Vevor Heater Auto Start/Stop switch.

    When enabled in Temperature mode, the heater will completely stop
    when the room temperature reaches 2°C above the target, and restart
    when it drops 2°C below the target.

    Without this, the heater only reduces power to level 1 but keeps running.
    """

    _attr_has_entity_name = True
    _attr_name = "Auto Start/Stop"
    _attr_icon = "mdi:thermostat-auto"

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_auto_start_stop"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Auto Start/Stop is only relevant in Temperature mode.
        """
        if not self.coordinator.data.get("connected", False):
            return False
        # Only show as available in Temperature mode
        return self.coordinator.data.get("running_mode") == RUNNING_MODE_TEMPERATURE

    @property
    def is_on(self) -> bool | None:
        """Return true if auto start/stop is enabled."""
        return self.coordinator.data.get("auto_start_stop")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto start/stop."""
        await self.coordinator.async_set_auto_start_stop(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto start/stop."""
        await self.coordinator.async_set_auto_start_stop(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorAutoOffsetSwitch(CoordinatorEntity[VevorHeaterCoordinator], SwitchEntity):
    """Vevor Heater Auto Temperature Offset switch.

    When enabled, the integration automatically calculates and sends temperature
    offset commands to the heater based on an external temperature sensor.
    This makes the heater's control board use a more accurate temperature
    for its auto-start/stop logic.

    Requires an external temperature sensor to be configured in the integration
    options.
    """

    _attr_has_entity_name = True
    _attr_name = "Auto Temperature Offset"
    _attr_icon = "mdi:thermometer-auto"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_auto_offset"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Auto offset only works when an external sensor is configured.
        """
        if not self.coordinator.data.get("connected", False):
            return False
        # Only show as available if external sensor is configured
        external_sensor = self.coordinator.config_entry.data.get(CONF_EXTERNAL_TEMP_SENSOR, "")
        return bool(external_sensor)

    @property
    def is_on(self) -> bool | None:
        """Return true if auto offset is enabled."""
        return self.coordinator.data.get("auto_offset_enabled", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto offset."""
        await self.coordinator.async_set_auto_offset_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto offset."""
        await self.coordinator.async_set_auto_offset_enabled(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorTempUnitSwitch(CoordinatorEntity[VevorHeaterCoordinator], SwitchEntity):
    """Vevor Heater Temperature Unit switch.

    When ON: Fahrenheit
    When OFF: Celsius
    """

    _attr_has_entity_name = True
    _attr_name = "Fahrenheit Mode"
    _attr_icon = "mdi:temperature-fahrenheit"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_temp_unit"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if using Fahrenheit."""
        temp_unit = self.coordinator.data.get("temp_unit")
        if temp_unit is not None:
            return temp_unit == 1  # 1 = Fahrenheit
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch to Fahrenheit."""
        await self.coordinator.async_set_temp_unit(use_fahrenheit=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch to Celsius."""
        await self.coordinator.async_set_temp_unit(use_fahrenheit=False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorAltitudeUnitSwitch(CoordinatorEntity[VevorHeaterCoordinator], SwitchEntity):
    """Vevor Heater Altitude Unit switch.

    When ON: Feet
    When OFF: Meters
    """

    _attr_has_entity_name = True
    _attr_name = "Feet Mode"
    _attr_icon = "mdi:altimeter"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_altitude_unit"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if using Feet."""
        altitude_unit = self.coordinator.data.get("altitude_unit")
        if altitude_unit is not None:
            return altitude_unit == 1  # 1 = Feet
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch to Feet."""
        await self.coordinator.async_set_altitude_unit(use_feet=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch to Meters."""
        await self.coordinator.async_set_altitude_unit(use_feet=False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class VevorHighAltitudeSwitch(CoordinatorEntity[VevorHeaterCoordinator], SwitchEntity):
    """Vevor Heater High Altitude Mode switch (ABBA/HeaterCC only).

    Enables high altitude compensation for heaters operating at
    high elevations where air density is lower.
    """

    _attr_has_entity_name = True
    _attr_name = "High Altitude Mode"
    _attr_icon = "mdi:image-filter-hdr"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: VevorHeaterCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_high_altitude"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": "Vevor Diesel Heater",
            "manufacturer": "Vevor",
            "model": "Diesel Heater",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available (ABBA devices only)."""
        if not self.coordinator.data.get("connected", False):
            return False
        return self.coordinator._is_abba_device

    @property
    def is_on(self) -> bool | None:
        """Return true if high altitude mode is enabled."""
        high_alt = self.coordinator.data.get("high_altitude")
        if high_alt is not None:
            return high_alt == 1
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable high altitude mode."""
        await self.coordinator.async_set_high_altitude(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable high altitude mode."""
        await self.coordinator.async_set_high_altitude(False)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
