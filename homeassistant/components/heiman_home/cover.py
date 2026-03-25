"""Cover entities for Heiman Home Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
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
    """Set up Heiman Home covers."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.info("Setting up Heiman Home covers for entry: %s", entry_id)

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

        # Add cover entities based on device properties with device config
        cover_entities = heiman_device.get_cover_entities(devices_config=devices_config)
        entities.extend(cover_entities)

    _LOGGER.info("Adding %s cover entities for entry %s", len(entities), entry_id)

    if entities:
        async_add_entities(entities)


class HeimanCoverEntity(CoordinatorEntity, CoverEntity):
    """Representation of a Heiman cover."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize cover."""
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

        # Set supported features based on property capabilities
        self._attr_supported_features = CoverEntityFeature(0)
        if property_info.get("supports_open"):
            self._attr_supported_features |= CoverEntityFeature.OPEN
        if property_info.get("supports_close"):
            self._attr_supported_features |= CoverEntityFeature.CLOSE
        if property_info.get("supports_stop"):
            self._attr_supported_features |= CoverEntityFeature.STOP
        if property_info.get("supports_position"):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
        if property_info.get("supports_tilt"):
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION

        # Set device class
        device_class = property_info.get("device_class")
        if device_class:
            self._attr_device_class = device_class

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
                "Added firmware version %s to cover device info for %s",
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
        self._attr_current_cover_position = None
        self._attr_is_closed = None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        # Try to get value from coordinator cache
        if self.coordinator and self.coordinator.device_data:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")
            return self.coordinator.device_data.get(device_id, {}).get(property_id)
        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        if self.coordinator and self.coordinator.device_data:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")
            value = self.coordinator.device_data.get(device_id, {}).get(property_id)
            if value is not None:
                # Convert to percentage (0-100)
                if isinstance(value, (int, float)):
                    return int(value)
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        open_value = self._property_info.get("open_value", 100)
        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=open_value,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        close_value = self._property_info.get("close_value", 0)
        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=close_value,
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        stop_value = self._property_info.get("stop_value", 50)
        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=stop_value,
        )

    async def async_set_cover_position(self, position: int, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")

        await self._cloud_client.mqtt_client.async_write_property(
            device_id=device_id,
            property_id=property_id,
            value=position,
        )
