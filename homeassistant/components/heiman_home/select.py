"""Select entities for Heiman Home Integration."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
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
    """Set up Heiman Home selects."""
    entry_id = config_entry.entry_id
    devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

    _LOGGER.debug("Setting up Heiman Home selects for entry: %s", entry_id)

    # Convert devices dict to list if needed
    if isinstance(devices_dict, dict):
        devices = list(devices_dict.values())
    else:
        devices = devices_dict if isinstance(devices_dict, list) else []

    _LOGGER.debug("Total devices for selects: %s", len(devices))

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

        # Add select entities based on device properties with device config
        select_entities = heiman_device.get_select_entities(
            devices_config=devices_config,
        )
        _LOGGER.debug(
            "  Device %s has %s select entities",
            device_name,
            len(select_entities),
        )
        entities.extend(select_entities)

    _LOGGER.debug("Adding %s select entities for entry %s", len(entities), entry_id)

    if not entities:
        _LOGGER.debug("No select entities were created for entry %s", entry_id)
    else:
        for entity in entities[:10]:  # Log first 10 entities
            _LOGGER.debug("  Entity: %s (unique_id: %s)", entity.name, entity.unique_id)

    async_add_entities(entities)


class HeimanSelectEntity(CoordinatorEntity, SelectEntity):
    """Representation of a Heiman select entity."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize select entity."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._property_info = property_info
        self._cloud_client = cloud_client
        self._i18n = i18n
        self._devices_config = devices_config or {}

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

        property_id = property_info.get("id", "")
        property_name = property_info.get("name", "")
        translated_property = i18n.translate_property(property_name)

        self._attr_unique_id = f"{device_id}_{property_id}"
        self._attr_name = (
            f"{device_name} {translated_property}"
            if translated_property
            else device_name
        )

        # Options from value_list (list of display strings)
        options = property_info.get("options", [])
        self._attr_options = options

        # Store value_list mapping (description -> value)
        self._value_list = property_info.get("value_list", {})
        # Also store reverse mapping (value -> description) for current_option
        self._reverse_value_list = property_info.get("reverse_value_list", {})

        # Debug logging for AlarmSoundOption
        if property_id == "AlarmSoundOption":
            _LOGGER.debug(
                "AlarmSoundOption initialized: options=%s, value_list=%s, reverse_value_list=%s",
                options,
                self._value_list,
                self._reverse_value_list,
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
                "Added firmware version %s to select device info for %s",
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

        # Initialize current option from coordinator cache
        self._current_option = None
        if coordinator:
            self._update_current_option_from_cache()
            # If cache is empty, schedule a coordinator refresh to fetch initial data
            if not self._update_current_option_from_cache() and coordinator:
                _LOGGER.debug(
                    "Cache miss for %s during initialization, scheduling coordinator refresh",
                    self._attr_name,
                )
                # Schedule a refresh without awaiting (fire-and-forget)
                if hasattr(self, "hass") and self.hass:
                    self.hass.async_create_task(coordinator.async_refresh())

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def should_poll(self) -> bool:
        """Return if polling is needed."""
        # Disable polling - rely on MQTT push and coordinator refresh
        return False

    def _update_current_option_from_cache(self) -> bool:
        """Update current option from coordinator cache (synchronous).

        Returns True if state was updated from cache, False if cache miss.
        """
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        property_id = self._property_info.get("id", "")

        # Normal select entity processing
        if self.coordinator and hasattr(self.coordinator, "get_device_property"):
            cached_value = self.coordinator.get_device_property(device_id, property_id)

            if cached_value is not None:
                # Convert value to description (option text)
                old_option = self._current_option
                self._current_option = self._get_description(value=cached_value)
                _LOGGER.debug("self._current_option %s", self._current_option)
                if self._current_option != old_option:
                    _LOGGER.debug(
                        "Selectxx %s current_option updated from cache: %s (value=%s)",
                        self._attr_name,
                        self._current_option,
                        cached_value,
                    )
                return True
        return False

    def _get_description(self, value) -> str | None:
        """Get description (option text) from value."""
        if value is None:
            return None
        # Try reverse_value_list first (value -> description)
        str_value = str(value)

        # Debug logging for AlarmSoundOption
        if self._property_info.get("id") == "AlarmSoundOption":
            _LOGGER.debug(
                "AlarmSoundOption _get_description: value=%s, str_value=%s, reverse_value_list=%s",
                value,
                str_value,
                self._reverse_value_list,
            )

        if str_value in self._reverse_value_list:
            result = self._reverse_value_list[str_value]
            if self._property_info.get("id") == "AlarmSoundOption":
                _LOGGER.debug(
                    "AlarmSoundOption found in reverse_value_list: %s -> %s",
                    str_value,
                    result,
                )
            return result
        # Fallback: try value_list (description -> value) in case they're the same
        for desc, val in self._value_list.items():
            if str(val) == str_value:
                if self._property_info.get("id") == "AlarmSoundOption":
                    _LOGGER.debug(
                        "AlarmSoundOption found in value_list: %s -> %s",
                        str_value,
                        desc,
                    )
                return desc
        # If no mapping found, return the value itself as string
        if self._property_info.get("id") == "AlarmSoundOption":
            _LOGGER.warning(
                "AlarmSoundOption no mapping found for value: %s, returning as string",
                str_value,
            )
        return str_value

    def _get_value(self, description: str):
        """Get value from description (option text)."""
        # Try value_list first (description -> value)
        if description in self._value_list:
            result = self._value_list[description]
            if self._property_info.get("id") == "AlarmSoundOption":
                _LOGGER.debug(
                    "AlarmSoundOption _get_value: %s -> %s",
                    description,
                    result,
                )
            return result
        # If not found, return the description itself
        if self._property_info.get("id") == "AlarmSoundOption":
            _LOGGER.warning(
                "AlarmSoundOption _get_value no mapping found for: %s, returning as is",
                description,
            )
        return description

    @property
    def current_option(self) -> str | None:
        """Return the current selected option.

        This should only return information from memory (not do I/O).
        """
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        property_id = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        product_id = self._device_info.get("productId", "")

        # Get the actual value for this option
        value = self._get_value(description=option)

        _LOGGER.debug(
            "Select %s setting option: %s -> value: %s",
            self._attr_name,
            option,
            value,
        )

        await self._cloud_client.mqtt_client.async_write_property(
            product_id=product_id,
            device_id=device_id,
            property_name=property_id,
            value=value,
        )

        # Update current option immediately for better UX
        self._current_option = option
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).

        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        try:
            device_id = self._device_info.get("id") or self._device_info.get(
                "deviceId",
                "",
            )
            property_id = self._property_info.get("id", "")

            _LOGGER.debug(
                "Select %s received coordinator update notification for device %s, property %s",
                self._attr_name,
                device_id,
                property_id,
            )

            # Only write state if cache update was successful (value changed)
            if self._update_current_option_from_cache():
                _LOGGER.debug(
                    "Select %s updated from coordinator (MQTT)",
                    self._attr_name,
                )
                # Write the new state to Home Assistant immediately
                self.async_write_ha_state()
            else:
                _LOGGER.debug(
                    "Select %s no value change from coordinator update",
                    self._attr_name,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "Error handling coordinator update for %s: %s",
                self._attr_name,
                err,
            )
