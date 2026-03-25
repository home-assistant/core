"""Climate entities for Heiman Home Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman Home climate entities."""
    entry_id = config_entry.entry_id

    _LOGGER.debug("Setting up Heiman Home climate entities for entry: %s", entry_id)

    # TODO: Implement actual climate entity setup when climate devices are available
    # For now, just return successfully to avoid blocking other platforms
    # entities = []
    # async_add_entities(entities)

    return True


class HeimanClimateEntity(CoordinatorEntity, ClimateEntity):
    """Representation of a Heiman climate device."""

    def __init__(self, coordinator, device_info: dict, cloud_client) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._cloud_client = cloud_client
        self._attr_unique_id = f"{device_info['deviceId']}_climate"
        self._attr_name = device_info.get("name", "Unknown Climate")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_info["deviceId"])},
            "name": device_info.get("name", "Unknown"),
            "manufacturer": "Heiman",
            "model": device_info.get("model", "Unknown"),
        }
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_temperature_unit = "°C"
        self._attr_target_temperature_step = 1.0
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            # TODO: Implement temperature setting via API/MQTT
            self._attr_target_temperature = temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        self._attr_hvac_mode = hvac_mode
        # TODO: Implement HVAC mode setting via API/MQTT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        # TODO: Implement based on device state
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # TODO: Get from device
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._attr_target_temperature

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device_info.get("online", False)

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        # Disable polling - rely on MQTT push and coordinator refresh
        return False

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend.

        Only returns device photo for main climate entities.
        Returns None if custom icon is set.
        """
        # If entity has a custom icon from _attr_icon, don't use device photo
        if self._attr_icon:
            return None

        # Get photoUrl from device info - check both direct field and nested fields
        photo_url = self._device_info.get("photoUrl")
        if photo_url:
            return photo_url
        # Also check in productInfo if available
        product_info = self._device_info.get("productInfo", {})
        if isinstance(product_info, dict):
            return product_info.get("photoUrl")
        return None
