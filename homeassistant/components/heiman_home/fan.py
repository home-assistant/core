"""Fan entities for Heiman Home Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import CONF_DEVICES_CONFIG, DEFAULT_INTEGRATION_LANGUAGE, DOMAIN
from .heiman_coordinator import get_coordinator
from .heiman_device import HeimanDevice
from .heiman_i18n import get_i18n

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman Home fans."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.info("Setting up Heiman Home fans for entry: %s", entry_id)

    # Convert devices dict to list if needed
    if isinstance(devices_dict, dict):
        devices = list(devices_dict.values())
    else:
        devices = devices_dict if isinstance(devices_dict, list) else []

    # Get language preference
    language = config_entry.options.get(
        "language",
        config_entry.data.get("language", DEFAULT_INTEGRATION_LANGUAGE),
    )
    i18n = get_i18n(language)

    devices_config = config_entry.data.get(CONF_DEVICES_CONFIG, {})

    get_coordinator(hass, entry_id)
    cloud_client = hass.data[DOMAIN]["clients"][entry_id]

    entities = []
    for device in devices:
        device.get("id") or device.get("deviceId", "")
        (
            device.get("deviceName")
            or device.get("name")
            or device.get("productName", "Unknown")
        )

        heiman_device = HeimanDevice(
            hass=hass,
            device_info=device,
            cloud_client=cloud_client,
            entry_id=entry_id,
            i18n=i18n,
        )

        # Add fan entities based on device properties with device config
        fan_entities = heiman_device.get_fan_entities(devices_config=devices_config)
        entities.extend(fan_entities)

    _LOGGER.info("Adding %s fan entities for entry %s", len(entities), entry_id)

    if entities:
        async_add_entities(entities)


class HeimanFanEntity(CoordinatorEntity, FanEntity):
    """Representation of a Heiman fan."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize fan."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._property_info = property_info
        self._cloud_client = cloud_client
        self._i18n = i18n
        self._devices_config = devices_config or {}

        property_id = property_info.get("id", "")
        property_name = property_info.get("name", "")

        # Get device ID from various possible fields (API uses 'id')
        device_id = device_info.get("id") or device_info.get("deviceId", "")
        device_name = (
            device_info.get("deviceName")
            or device_info.get("name")
            or device_info.get("productName", "Unknown")
        )
        device_model = (
            device_info.get("modelName")
            or device_info.get("model")
            or device_info.get("productName", "Unknown")
        )

        # Apply device config overrides if available
        device_config = self._devices_config.get(device_id, {})
        if device_config.get("name"):
            device_name = device_config["name"]

        # Use i18n to translate property name
        translated_property = i18n.translate_property(property_name)

        self._attr_unique_id = f"{device_id}_{property_id}"
        self._attr_name = (
            f"{device_name} {translated_property}"
            if translated_property
            else device_name
        )

        # Set supported features
        self._attr_supported_features = FanEntityFeature(0)
        if property_info.get("supports_turn_on"):
            self._attr_supported_features |= FanEntityFeature.TURN_ON
        if property_info.get("supports_turn_off"):
            self._attr_supported_features |= FanEntityFeature.TURN_OFF
        if property_info.get("supports_set_speed"):
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
        if property_info.get("supports_oscillate"):
            self._attr_supported_features |= FanEntityFeature.OSCILLATE
        if property_info.get("supports_preset_mode"):
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE

        # Speed settings
        self._speed_min = property_info.get("speed_min", 1)
        self._speed_max = property_info.get("speed_max", 3)
        self._attr_speed_count = self._speed_max - self._speed_min + 1

        # Preset modes
        preset_modes = property_info.get("preset_modes", [])
        if preset_modes:
            self._attr_preset_modes = preset_modes

        # Build device info with area support and firmware version
        device_info_dict = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Heiman",
            "model": device_model,
        }

        # Add firmware version if available
        sw_version = device_info.get("sw_version")
        if sw_version:
            device_info_dict["sw_version"] = sw_version
            _LOGGER.debug(
                "Added firmware version %s to fan device info for %s",
                sw_version,
                device_id,
            )

        # Add suggested_area from device config
        if device_config.get("area_id"):
            device_info_dict["suggested_area"] = device_config["area_id"]
        else:
            # Fallback to room name from device info
            room_name = device_info.get("room_name") or device_info.get("roomName", "")
            home_name = device_info.get("home_name") or device_info.get("homeName", "")
            if room_name and home_name:
                device_info_dict["suggested_area"] = f"{home_name} {room_name}"
            elif room_name:
                device_info_dict["suggested_area"] = room_name
            elif home_name:
                device_info_dict["suggested_area"] = home_name

        self._attr_device_info = device_info_dict
        self._attr_is_on = None
        self._attr_percentage = None
        self._attr_preset_mode = None
        self._attr_oscillating = None

    @property
    def is_on(self) -> bool | None:
        """Return if the fan is on."""
        if self.coordinator and self.coordinator.device_data:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")
            return self.coordinator.device_data.get(device_id, {}).get(property_id)
        return None

    @property
    def percentage(self) -> int | None:
        """Return the current percentage of the fan speed."""
        if self.coordinator and self.coordinator.device_data:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")
            value = self.coordinator.device_data.get(device_id, {}).get(property_id)
            if value is not None:
                return ranged_value_to_percentage(
                    low_high_range=(self._speed_min, self._speed_max),
                    value=value,
                )
        return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        # Turn on
        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=True,
        )

        # Set percentage if provided
        if percentage is not None:
            speed_value = int(
                percentage_to_ranged_value(
                    low_high_range=(self._speed_min, self._speed_max),
                    percentage=percentage,
                ),
            )
            await self._cloud_client.mqtt_client.async_write_property(
                device_id=device_id,
                property_id=property_id,
                value=speed_value,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=False,
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan speed."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        speed_value = int(
            percentage_to_ranged_value(
                low_high_range=(self._speed_min, self._speed_max),
                percentage=percentage,
            ),
        )

        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=speed_value,
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        property_id = self._property_info.get("oscillate_property_id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        if property_id:
            await self._cloud_client.mqtt_client.async_write_property(
                device_id=device_id,
                property_id=property_id,
                value=oscillating,
            )
