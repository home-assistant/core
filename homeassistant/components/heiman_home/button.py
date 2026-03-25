"""Button entities for Heiman Home Integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
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
    """Set up Heiman Home buttons."""
    try:
        entry_id = config_entry.entry_id

        _LOGGER.debug("=" * 80)
        _LOGGER.debug(
            "BUTTON PLATFORM: Starting async_setup_entry for entry: %s",
            entry_id,
        )
        _LOGGER.debug("=" * 80)

        # Check if DOMAIN data exists
        if DOMAIN not in hass.data:
            _LOGGER.error(
                "BUTTON PLATFORM ERROR: DOMAIN %s not found in hass.data",
                DOMAIN,
            )
            return False

        # Check if devices data exists
        if "devices" not in hass.data[DOMAIN]:
            _LOGGER.error(
                "BUTTON PLATFORM ERROR: 'devices' not found in hass.data[%s]",
                DOMAIN,
            )
            return False

        devices_dict = hass.data[DOMAIN]["devices"].get(entry_id, {})

        _LOGGER.debug("BUTTON PLATFORM: devices_dict = %s", devices_dict)

        if not devices_dict:
            _LOGGER.debug("BUTTON PLATFORM: No devices found for entry %s", entry_id)
            return True  # Return True to indicate success (no devices is not an error)

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

        # Get coordinator and cloud client
        _LOGGER.debug("BUTTON PLATFORM: Getting coordinator and cloud client")
        try:
            get_coordinator(hass, entry_id)
            cloud_client = hass.data[DOMAIN]["clients"][entry_id]
            _LOGGER.debug(
                "BUTTON PLATFORM: Successfully got coordinator and cloud client",
            )
        except Exception:
            _LOGGER.exception(
                "BUTTON PLATFORM ERROR: Failed to get coordinator or cloud client",
            )
            return False

        entities = []
        _LOGGER.debug("BUTTON PLATFORM: Processing %d devices", len(devices))

        # Try to use pre-initialized device objects
        initialized_devices = (
            hass.data[DOMAIN].get("heiman_devices", {}).get(entry_id, {})
        )
        _LOGGER.debug(
            "BUTTON PLATFORM: Found %d pre-initialized devices",
            len(initialized_devices),
        )

        for idx, device in enumerate(devices):
            try:
                device_id = device.get("id") or device.get("deviceId", "")
                device_name = (
                    device.get("deviceName")
                    or device.get("name")
                    or device.get("productName", "Unknown")
                )

                _LOGGER.debug(
                    "BUTTON PLATFORM: Processing device %d/%d: %s (%s)",
                    idx + 1,
                    len(devices),
                    device_id,
                    device_name,
                )

                # Use pre-initialized device if available
                if device_id in initialized_devices:
                    heiman_device = initialized_devices[device_id]
                    _LOGGER.debug(
                        "BUTTON PLATFORM: Using pre-initialized device for %s",
                        device_id,
                    )
                else:
                    heiman_device = HeimanDevice(
                        hass=hass,
                        device_info=device,
                        cloud_client=cloud_client,
                        entry_id=entry_id,
                        i18n=i18n,
                    )
                    # Initialize properties for new device
                    await heiman_device.async_init_properties()
                    _LOGGER.debug(
                        "BUTTON PLATFORM: Created and initialized new device for %s",
                        device_id,
                    )

                # Add button entities based on device properties with device config
                try:
                    button_entities = heiman_device.get_button_entities(
                        devices_config=devices_config,
                    )
                    _LOGGER.debug(
                        "BUTTON PLATFORM: Device %s has %d button entities",
                        device_id,
                        len(button_entities),
                    )
                    entities.extend(button_entities)

                    if button_entities:
                        _LOGGER.debug(
                            "BUTTON PLATFORM: Device %s button properties: %s",
                            device_id,
                            [btn.unique_id for btn in button_entities],
                        )
                except Exception:
                    _LOGGER.exception(
                        "BUTTON PLATFORM ERROR: Failed to get button entities for device %s",
                        device_id,
                    )
                    continue

            except Exception:
                _LOGGER.exception(
                    "BUTTON PLATFORM ERROR: Failed to process device %s",
                    device.get("id") or device.get("deviceId", "unknown"),
                )
                continue

        _LOGGER.debug(
            "BUTTON PLATFORM: Total %s button entities to add for entry %s",
            len(entities),
            entry_id,
        )

        if entities:
            _LOGGER.debug(
                "BUTTON PLATFORM: About to call async_add_entities with %d entities",
                len(entities),
            )
            for idx, e in enumerate(entities):
                _LOGGER.debug(
                    "BUTTON PLATFORM: Entity %d: %s (unique_id: %s)",
                    idx,
                    e.name,
                    e.unique_id,
                )
            try:
                async_add_entities(entities)
                _LOGGER.debug("BUTTON PLATFORM: async_add_entities called successfully")
            except Exception:
                _LOGGER.exception(
                    "BUTTON PLATFORM ERROR: Failed to call async_add_entities",
                )
                return False
        else:
            _LOGGER.debug(
                "BUTTON PLATFORM: No button entities to add for entry %s",
                entry_id,
            )

        _LOGGER.debug(
            "BUTTON PLATFORM: async_setup_entry completed successfully for entry %s",
            entry_id,
        )

    except Exception:
        _LOGGER.exception("BUTTON PLATFORM FATAL ERROR in async_setup_entry")
        return False
    else:
        return True


class HeimanButtonEntity(CoordinatorEntity, ButtonEntity):
    """Representation of a Heiman button."""

    def __init__(
        self,
        coordinator,
        device_info: dict,
        property_info: dict,
        cloud_client,
        i18n,
        devices_config: dict | None = None,
    ) -> None:
        """Initialize button."""
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
        self._attr_icon = _get_button_icon(property_info) or property_info.get("icon")
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
                "Added firmware version %s to button device info for %s",
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

    async def async_press(self) -> None:
        """Handle the button press."""
        property_name = self._property_info.get("id", "")
        device_id = self._device_info.get("id") or self._device_info.get("deviceId", "")
        product_id = self._device_info.get("productId", "")

        # Get device info from cloud client for child device detection
        device_info = None
        if hasattr(self._cloud_client, "devices"):
            device_info = self._cloud_client.devices.get(device_id)

        # Write property via MQTT
        if self._cloud_client.mqtt_client:
            await self._cloud_client.mqtt_client.async_write_property(
                product_id=product_id,
                device_id=device_id,
                property_name=property_name,
                value=self._property_info.get("on_value", 1),
                device_info=device_info,
            )
        else:
            _LOGGER.error("MQTT client not available for button press")


def _get_button_icon(property_info: dict) -> str | None:
    """Get icon for button entity based on property name.

    Args:
        property_info: Property information dictionary containing 'name' or 'id'

    Returns:
        MDI icon string or None to use default icon
    """
    property_name = property_info.get("name", "").lower()
    property_id = property_info.get("id", "").lower()
    _LOGGER.info("  property_id %s property_name %s", property_id, property_name)

    # Check both name and id fields
    check_text = f"{property_name} {property_id}".lower()

    # LED indicator light
    if "led" in check_text or "indicator" in check_text:
        return "mdi:led-on"

    # Locate/Paging function
    if "locate" in check_text or "page" in check_text or "find" in check_text:
        return "mdi:radar"

    # Mute function
    if "mute" in check_text or "silent" in check_text:
        return "mdi:volume-mute"

    # Self-test function
    if (
        "self-test" in check_text
        or "selftest" in check_text
        or "remotecheck" in check_text
        or "test" in check_text
    ):
        return "mdi:clipboard-check-outline"

    # Power switch
    if "power" in check_text or "switch" in check_text:
        return "mdi:power-socket"

    # Default: use generic switch icon
    return "mdi:toggle-switch"
