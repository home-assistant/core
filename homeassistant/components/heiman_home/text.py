"""Text entities for Heiman Home Integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import get_initialized_device
from .const import CONF_DEVICES_CONFIG, DEFAULT_INTEGRATION_LANGUAGE, DOMAIN
from .heiman_coordinator import get_coordinator
from .heiman_i18n import get_i18n

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman Home text entities."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.debug("Setting up Heiman Home text entities for entry: %s", entry_id)

    # Convert devices dict to list if needed
    if isinstance(devices_dict, dict):
        devices = list(devices_dict.values())
    else:
        devices = devices_dict if isinstance(devices_dict, list) else []

    _LOGGER.debug(
        "Total devices in hass.data[DOMAIN]['devices'][%s]: %s",
        entry_id,
        len(devices),
    )

    # Get language preference
    language = config_entry.options.get(
        "language",
        config_entry.data.get("language", DEFAULT_INTEGRATION_LANGUAGE),
    )
    i18n = get_i18n(language)

    devices_config = config_entry.data.get(CONF_DEVICES_CONFIG, {})

    # Get coordinator and cloud client
    get_coordinator(hass, entry_id)
    cloud_client = hass.data[DOMAIN]["clients"][entry_id]

    entities = []

    for device in devices:
        device_id = device.get("id") or device.get("deviceId", "")
        device_name = (
            device.get("deviceName")
            or device.get("name")
            or device.get("productName", "Unknown")
        )
        device_model = (
            device.get("modelName")
            or device.get("model")
            or device.get("productName", "")
        )

        _LOGGER.debug(
            "Processing device: ID=%s, Name=%s, Model=%s",
            device_id,
            device_name,
            device_model,
        )

        # Reuse initialized device object from hass.data
        heiman_device = get_initialized_device(
            hass=hass,
            entry_id=entry_id,
            device_id=device_id,
            device_info=device,
            cloud_client=cloud_client,
            i18n=i18n,
        )

        # Add text entities based on device properties with device config
        text_entities = heiman_device.get_text_entities(devices_config=devices_config)
        _LOGGER.debug(
            "  Device %s has %s text entities",
            device_name,
            len(text_entities),
        )
        entities.extend(text_entities)

    _LOGGER.info("Adding %s text entities for entry %s", len(entities), entry_id)

    if not entities:
        _LOGGER.debug("No text entities were created for entry %s", entry_id)
    else:
        for entity in entities:
            _LOGGER.debug("  Entity: %s (unique_id: %s)", entity.name, entity.unique_id)

    async_add_entities(entities)


class HeimanTextEntity(CoordinatorEntity, TextEntity):
    """Representation of a Heiman text entity."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize text entity."""
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

        # Set icon from property info
        self._attr_icon = property_info.get("icon")

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
                "Added firmware version %s to text device info for %s",
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

        # Set text-specific attributes
        self._attr_native_value = None
        self._attr_mode = "text"
        self._attr_native_min = 0
        self._attr_native_max = 100
        self._attr_pattern = None

        # Try to get initial value from coordinator cache
        if coordinator:
            self._update_from_cache()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        # Disable polling - rely on MQTT push and coordinator refresh
        return False

    def _normalize_text_value(self, value: Any) -> str | None:
        """Normalize text value to a valid state type.

        Home Assistant text entity state must be a string.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value
        # Convert other types to string
        return str(value)

    def _update_from_cache(self) -> bool:
        """Update entity state from coordinator cache (synchronous).

        Returns True if state was updated from cache, False if cache miss.
        """
        # Get device ID from various possible fields
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        property_id = self._property_info.get("id", "")
        parent_property = self._property_info.get("parent_property")
        json_field = self._property_info.get("json_field")

        # Get property value from coordinator cache
        if self.coordinator and hasattr(self.coordinator, "data"):
            device_data = self.coordinator.data.get(device_id, {})

            # Handle nested properties (like DeviceINFO_MAC, DeviceINFO_IP)
            if parent_property and json_field:
                parent_data = device_data.get(parent_property, {})
                if isinstance(parent_data, dict):
                    cached_value = parent_data.get(json_field)
                    if cached_value is not None:
                        normalized_value = self._normalize_text_value(cached_value)
                        if self._attr_native_value != normalized_value:
                            self._attr_native_value = normalized_value
                            _LOGGER.debug(
                                "Text %s updated from cache: %s = %s",
                                self._attr_name,
                                property_id,
                                cached_value,
                            )
                        return True

            # Handle direct properties
            cached_value = device_data.get(property_id)
            if cached_value is not None:
                normalized_value = self._normalize_text_value(cached_value)
                if self._attr_native_value != normalized_value:
                    self._attr_native_value = normalized_value
                    _LOGGER.debug(
                        "Text %s updated from cache: %s = %s",
                        self._attr_name,
                        property_id,
                        cached_value,
                    )
                return True

        return False

    @property
    def native_value(self) -> str | None:
        """Return the current text value."""
        # First try to use cached value
        if self._attr_native_value is not None:
            return self._attr_native_value

        # Try to get value from coordinator data
        if self.coordinator and hasattr(self.coordinator, "data"):
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")
            parent_property = self._property_info.get("parent_property")
            json_field = self._property_info.get("json_field")

            device_data = self.coordinator.data.get(device_id, {})

            # Handle nested properties (like DeviceINFO_MAC, DeviceINFO_IP)
            if parent_property and json_field:
                parent_data = device_data.get(parent_property, {})
                if isinstance(parent_data, dict):
                    value = parent_data.get(json_field)
                    if value is not None:
                        return self._normalize_text_value(value)

            # Handle direct properties
            value = device_data.get(property_id)
            if value is not None:
                return self._normalize_text_value(value)

        return None

    async def async_set_value(self, value: str) -> None:
        """Update the current value."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        product_id = self._device_info.get("productId", "")

        _LOGGER.debug(
            "Setting text value for %s: %s = %s",
            self._attr_name,
            property_id,
            value,
        )

        await self._cloud_client.mqtt_client.async_write_property(
            product_id=product_id,
            device_id=device_id,
            property_name=property_id,
            value=value,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        # Only write state if cache update was successful (value changed)
        if self._update_from_cache():
            _LOGGER.debug("Text %s updated from coordinator (MQTT)", self._attr_name)
            # Write the new state to Home Assistant immediately
            self.async_write_ha_state()
