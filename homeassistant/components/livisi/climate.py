"""Code to handle a Livisi Virtual Climate Control."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiolivisi.const import CAPABILITY_MAP

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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    VRCC_DEVICE_TYPE,
)
from .coordinator import LivisiDataUpdateCoordinator


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
                livisi_climate: ClimateEntity = create_entity(
                    config_entry, device, coordinator
                )
                LOGGER.debug("Include device type: %s", device.get("type"))
                coordinator.devices.add(device["id"])
                entities.append(livisi_climate)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


def create_entity(
    config_entry: ConfigEntry,
    device: dict[str, Any],
    coordinator: LivisiDataUpdateCoordinator,
) -> ClimateEntity:
    """Create Climate Entity."""
    capabilities: Mapping[str, Any] = device[CAPABILITY_MAP]
    room_id: str = device["location"]
    room_name: str = coordinator.rooms[room_id]
    livisi_climate = LivisiClimate(
        config_entry,
        coordinator,
        unique_id=device["id"],
        manufacturer=device["manufacturer"],
        device_type=device["type"],
        target_temperature_capability=capabilities["RoomSetpoint"],
        temperature_capability=capabilities["RoomTemperature"],
        humidity_capability=capabilities["RoomHumidity"],
        room=room_name,
    )
    return livisi_climate


class LivisiClimate(CoordinatorEntity[LivisiDataUpdateCoordinator], ClimateEntity):
    """Represents the Livisi Climate."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        unique_id: str,
        manufacturer: str,
        device_type: str,
        target_temperature_capability: str,
        temperature_capability: str,
        humidity_capability: str,
        room: str,
    ) -> None:
        """Initialize the Livisi Climate."""
        self.config_entry = config_entry
        self._attr_unique_id = unique_id
        self._target_temperature_capability = target_temperature_capability
        self._temperature_capability = temperature_capability
        self._humidity_capability = humidity_capability
        self.aio_livisi = coordinator.aiolivisi
        self._attr_available = False
        self._attr_hvac_modes = [HVACMode.HEAT]
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_target_temperature_high = MAX_TEMPERATURE
        self._attr_target_temperature_low = MIN_TEMPERATURE
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=manufacturer,
            model=device_type,
            name=room,
            suggested_area=room,
            via_device=(DOMAIN, config_entry.entry_id),
        )
        super().__init__(coordinator)

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

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Do nothing as LIVISI devices do not support changing the hvac mode."""
        raise HomeAssistantError(
            "This feature is not supported with the LIVISI climate devices"
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        target_temperature = await self.coordinator.async_get_vrcc_target_temperature(
            self._target_temperature_capability
        )
        temperature = await self.coordinator.async_get_vrcc_temperature(
            self._temperature_capability
        )
        humidity = await self.coordinator.async_get_vrcc_humidity(
            self._humidity_capability
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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{self.unique_id}",
                self.update_reachability,
            )
        )

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
        """Update the humidity temperature of the climate device."""
        self._attr_current_humidity = humidity
        self.async_write_ha_state()

    @callback
    def update_reachability(self, is_reachable: bool) -> None:
        """Update the reachability of the climate device."""
        self._attr_available = is_reachable
        self.async_write_ha_state()
