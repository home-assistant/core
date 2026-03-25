"""Binary Sensor entities for Heiman Home Integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import get_initialized_device
from .const import CONF_DEVICES_CONFIG, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman Home binary sensors."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.info("Setting up Heiman Home binary sensors for entry: %s", entry_id)

    # Convert devices dict to list if needed
    if isinstance(devices_dict, dict):
        devices = list(devices_dict.values())
    else:
        devices = devices_dict if isinstance(devices_dict, list) else []

    _LOGGER.info("Total devices for binary sensors: %s", len(devices))

    devices_config = config_entry.data.get(CONF_DEVICES_CONFIG, {})

    entities = []

    for device in devices:
        device_name = (
            device.get("deviceName")
            or device.get("name")
            or device.get("productName", "Unknown")
        )
        device_id = device.get("id") or device.get("deviceId", "")

        # Reuse initialized device object from hass.data
        heiman_device = get_initialized_device(
            hass=hass,
            entry_id=entry_id,
            device_id=device_id,
            device_info=device,
            cloud_client=hass.data[DOMAIN]["clients"][entry_id],
        )

        # Add binary sensor entities based on device properties with device config
        binary_sensor_entities = heiman_device.get_binary_sensor_entities(
            devices_config=devices_config,
        )
        _LOGGER.debug(
            "  Device %s has %s binary sensor entities",
            device_name,
            len(binary_sensor_entities),
        )
        entities.extend(binary_sensor_entities)

    _LOGGER.info("Adding %s binary sensor entities", len(entities))
    async_add_entities(entities)


class HeimanBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Heiman binary sensor."""

    # Mapping of property IDs to translation keys for custom state text
    # Format: "PropertyID": "translation_key"
    # Translation keys are used to look up state strings in translations/*.json
    TRANSLATION_KEYS = {
        "TamperState": "tamper",
        # Add more property mappings here:
        # "SmokeSensorState": "smoke",
        # "BatteryState": "battery",
        # "LowBattery": "battery_low",
    }

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        device_class: str | None = None,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._property_info = property_info
        self._cloud_client = cloud_client
        self._devices_config = devices_config or {}
        self._property_id = property_info["id"]

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

        self._attr_unique_id = f"{device_id}_{self._property_id}"
        self._attr_name = f"{device_name} {property_info.get('name', '')}"

        # Set icon from property info
        self._attr_icon = property_info.get("icon")
        if device_id == "1942869486798540800":
            _LOGGER.info(
                "  _attr_unique_id %s has icon %s",
                self._attr_unique_id,
                self._attr_icon,
            )
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
                "Added firmware version %s to binary sensor device info for %s",
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
        self._attr_is_on = False
        if device_class:
            self._attr_device_class = device_class

        # Try to get initial value from coordinator cache
        if coordinator:
            self._update_from_cache()
            # If cache is empty, schedule a coordinator refresh to fetch initial data
            if not self._update_from_cache() and coordinator:
                _LOGGER.debug(
                    "Cache miss for %s during initialization, scheduling coordinator refresh",
                    self._attr_name,
                )
                # Schedule a refresh without awaiting (fire-and-forget)
                if hasattr(self, "hass") and self.hass:
                    self.hass.async_create_task(coordinator.async_refresh())

    def _get_translation_key(self) -> str | None:
        """Get the translation key for this property.

        Returns the translation key if this property has custom state text,
        otherwise returns None.
        """
        return self.TRANSLATION_KEYS.get(self._property_id)

    @property
    def translation_key(self) -> str | None:
        """Return the translation key for this entity.

        This enables Home Assistant to use translated state strings.
        """
        return self._get_translation_key()

    # @property
    # def entity_picture(self) -> str | None:
    #     """Return the entity picture to use in the frontend.
    #
    #     Only returns device photo for main binary sensor entities.
    #     Returns None for diagnostic and functional sensors to use their custom icons instead.
    #     """
    #     # List of property IDs/names that should use custom icons instead of device photo
    #     icon_properties = {
    #         'low_battery', 'battery', 'fault', 'tamper', 'error',
    #         'underVolt', 'volt', 'voltage'
    #     }
    #
    #     property_id = self._property_info.get('id', '').lower()
    #     property_name = self._property_info.get('name', '').lower()
    #
    #     # Check if this property should use a custom icon
    #     check_text = f"{property_name} {property_id}".lower()
    #     if any(icon_prop in check_text for icon_prop in icon_properties):
    #         return None
    #
    #     # Get photoUrl from device info - check both direct field and nested fields
    #     photo_url = self._device_info.get('photoUrl')
    #     if photo_url:
    #         return photo_url
    #     # Also check in productInfo if available
    #     product_info = self._device_info.get('productInfo', {})
    #     if isinstance(product_info, dict):
    #         return product_info.get('photoUrl')
    #     return None

    def _update_from_cache(self) -> bool:
        """Update entity state from coordinator cache (synchronous).

        Returns True if state was updated from cache, False if cache miss.
        This is used by both polling and MQTT push, but only reads from cache.
        For API fallback, the logic is in async_update().
        """
        # Get device ID from various possible fields
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        property_name = self._property_info["id"]

        _LOGGER.debug(
            "_update_from_cache: device_id=%s, property_name=%s, coordinator=%s",
            device_id,
            property_name,
            self.coordinator is not None,
        )

        # Get property value from coordinator cache
        if self.coordinator and hasattr(self.coordinator, "get_device_property"):
            cached_value = self.coordinator.get_device_property(
                device_id,
                property_name,
            )
            _LOGGER.debug(
                "_update_from_cache: got cached_value=%s for %s.%s",
                cached_value,
                device_id,
                property_name,
            )
            if cached_value is not None:
                if cached_value == 1:
                    self._attr_is_on = True
                else:
                    self._attr_is_on = False
                #
                # self._attr_is_on = bool(cached_value)
                # _LOGGER.debug(
                #     "Binary sensor %s updated from cache: %s = %s",
                #     self._attr_name, property_name, cached_value
                # )
                # return True
            else:
                _LOGGER.debug(
                    "_update_from_cache: no cached value for %s.%s",
                    device_id,
                    property_name,
                )
        else:
            _LOGGER.debug(
                "_update_from_cache: no coordinator or get_device_property method",
            )

        return False

    async def async_update(self) -> None:
        """Fetch new state data for the binary sensor from coordinator cache.

        This is called during polling by Home Assistant.
        Note: HA automatically calls async_write_ha_state() after async_update().
        """
        try:
            if not self._update_from_cache():
                # 降级：单独请求（兼容旧设备或缓存未命中）
                _LOGGER.info(
                    "Binary sensor %s cache miss, falling back to individual API request",
                    self._attr_name,
                )
                device_id = self._device_info.get("id") or self._device_info.get(
                    "deviceId",
                    "",
                )
                property_name = self._property_info["id"]
                product_id = self._device_info.get("productId", "")
                result = await self._cloud_client.async_read_device_property(
                    product_id=product_id,
                    device_id=device_id,
                    property_name=property_name,
                )
                _LOGGER.info(
                    "Binary sensor %s updated from API: %s = %s",
                    self._attr_name,
                    property_name,
                    result,
                )
                if result and "value" in result:
                    self._attr_is_on = bool(result["value"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to update binary sensor %s: %s", self._attr_name, err)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        try:
            if self._update_from_cache():
                _LOGGER.debug(
                    "Binary sensor %s updated from coordinator (MQTT)",
                    self._attr_name,
                )
            # Write the new state to Home Assistant immediately
            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error handling coordinator update for %s: %s",
                self._attr_name,
                err,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Check device online state - API returns state object with 'value' field
        state = self._device_info.get("state", {})
        if isinstance(state, dict):
            return state.get("value") == "online"
        # Fallback to legacy 'online' field
        return self._device_info.get("online", False)

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        # Disable polling - rely on MQTT push and coordinator refresh
        return False
