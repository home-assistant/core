"""Light entities for Heiman Home Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    """Set up Heiman Home lights."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.info("Setting up Heiman Home lights for entry: %s", entry_id)

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

    # Get devices config for name/area overrides
    devices_config = config_entry.data.get(CONF_DEVICES_CONFIG, {})

    # Get coordinator and cloud client
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

        # Add light entities based on device properties with device config
        light_entities = heiman_device.get_light_entities(devices_config=devices_config)
        entities.extend(light_entities)

    _LOGGER.info("Adding %s light entities for entry %s", len(entities), entry_id)

    if entities:
        async_add_entities(entities)


class HeimanLightEntity(CoordinatorEntity, LightEntity):
    """Representation of a Heiman light."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize light."""
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

        # Set supported color modes
        self._attr_supported_color_modes = set()
        self._attr_color_mode = None
        self._attr_supported_features = LightEntityFeature(0)

        # Check capabilities
        if property_info.get("supports_brightness"):
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            self._attr_color_mode = ColorMode.BRIGHTNESS
        if property_info.get("supports_color_temp"):
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_min_color_temp_kelvin = property_info.get("min_color_temp", 2700)
            self._attr_max_color_temp_kelvin = property_info.get("max_color_temp", 6500)
        if property_info.get("supports_rgb"):
            self._attr_supported_color_modes.add(ColorMode.RGB)
            self._attr_color_mode = ColorMode.RGB

        # If no specific mode, default to ONOFF
        if not self._attr_supported_color_modes:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)
            self._attr_color_mode = ColorMode.ONOFF

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
                "Added firmware version %s to light device info for %s",
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
        self._attr_brightness = None
        self._attr_color_temp_kelvin = None
        self._attr_rgb_color = None

    @property
    def is_on(self) -> bool | None:
        """Return if the light is on."""
        if self.coordinator and self.coordinator.device_data:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")
            return self.coordinator.device_data.get(device_id, {}).get(property_id)
        return None

    @property
    def brightness(self) -> int | None:
        """Return the brightness."""
        if self.coordinator and self.coordinator.device_data:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            brightness_property_id = self._property_info.get(
                "brightness_property_id",
                "",
            )
            if brightness_property_id:
                value = self.coordinator.device_data.get(device_id, {}).get(
                    brightness_property_id,
                )
                if value is not None:
                    return int(value)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        # Turn on
        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=True,
        )

        # Set brightness if provided
        if ATTR_BRIGHTNESS in kwargs:
            brightness_property_id = self._property_info.get(
                "brightness_property_id",
                "",
            )
            if brightness_property_id:
                await self._cloud_client.mqtt_client.async_write_property(
                    device_id=device_id,
                    property_id=brightness_property_id,
                    value=kwargs[ATTR_BRIGHTNESS],
                )

        # Set color temperature if provided
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_property_id = self._property_info.get(
                "color_temp_property_id",
                "",
            )
            if color_temp_property_id:
                await self._cloud_client.mqtt_client.async_write_property(
                    device_id=device_id,
                    property_id=color_temp_property_id,
                    value=kwargs[ATTR_COLOR_TEMP_KELVIN],
                )

        # Set RGB color if provided
        if ATTR_RGB_COLOR in kwargs:
            rgb_property_id = self._property_info.get("rgb_property_id", "")
            if rgb_property_id:
                r = kwargs[ATTR_RGB_COLOR][0]
                g = kwargs[ATTR_RGB_COLOR][1]
                b = kwargs[ATTR_RGB_COLOR][2]
                rgb = (r << 16) | (g << 8) | b
                await self._cloud_client.mqtt_client.async_write_property(
                    device_id=device_id,
                    property_id=rgb_property_id,
                    value=rgb,
                )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=False,
        )
