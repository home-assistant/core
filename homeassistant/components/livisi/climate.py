"""Code to handle a Livisi Virtual Climate Control."""
from __future__ import annotations

from typing import Any

from aiolivisi.const import CAPABILITY_CONFIG

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    LIVISI_STATE_CHANGE,
    LOGGER,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    VRCC_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def handle_coordinator_update() -> None:
        """Add climate device."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[ClimateEntity] = []
        for device in shc_devices:
            if (
                device["type"] == VRCC_DEVICE_TYPE
                and device["id"] not in coordinator.devices
            ):
                livisi_climate: ClimateEntity = LivisiClimate(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s", device.get("type"))
                coordinator.devices.add(device["id"])
                entities.append(livisi_climate)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiClimate(LivisiEntity, ClimateEntity):
    """Represents the Livisi Climate."""

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi Climate."""
        super().__init__(
            config_entry, coordinator, device, use_room_as_device_name=True
        )

        self._target_temperature_capability = self.capabilities["RoomSetpoint"]
        self._temperature_capability = self.capabilities["RoomTemperature"]
        self._humidity_capability = self.capabilities["RoomHumidity"]

        config = device.get(CAPABILITY_CONFIG, {}).get("RoomSetpoint", {})
        self._attr_max_temp = config.get("maxTemperature", MAX_TEMPERATURE)
        self._attr_min_temp = config.get("minTemperature", MIN_TEMPERATURE)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        response = await self.aio_livisi.async_vrcc_set_temperature(
            self._target_temperature_capability,
            kwargs.get(ATTR_TEMPERATURE),
            self.coordinator.is_avatar,
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        await super().async_added_to_hass()

        target_temperature = await self.coordinator.async_get_device_state(
            self._target_temperature_capability,
            "setpointTemperature" if self.coordinator.is_avatar else "pointTemperature",
        )
        temperature = await self.coordinator.async_get_device_state(
            self._temperature_capability, "temperature"
        )
        humidity = await self.coordinator.async_get_device_state(
            self._humidity_capability, "humidity"
        )
        if temperature is None:
            self._attr_current_temperature = None
            self._attr_available = False
        else:
            self._attr_target_temperature = target_temperature
            self._attr_current_temperature = temperature
            self._attr_current_humidity = humidity
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._target_temperature_capability}",
                self.update_target_temperature,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._temperature_capability}",
                self.update_temperature,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._humidity_capability}",
                self.update_humidity,
            )
        )

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Do nothing as LIVISI devices do not support changing the hvac mode."""

    @callback
    def update_target_temperature(self, target_temperature: float) -> None:
        """Update the target temperature of the climate device."""
        self._attr_target_temperature = target_temperature
        self.async_write_ha_state()

    @callback
    def update_temperature(self, current_temperature: float) -> None:
        """Update the current temperature of the climate device."""
        self._attr_current_temperature = current_temperature
        self.async_write_ha_state()

    @callback
    def update_humidity(self, humidity: int) -> None:
        """Update the humidity of the climate device."""
        self._attr_current_humidity = humidity
        self.async_write_ha_state()
