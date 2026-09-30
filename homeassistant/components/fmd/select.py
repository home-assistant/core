"""Select entities for FMD integration."""

import asyncio
import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

COMMAND_PLACEHOLDER = "Send Command..."
RESET_DELAY = 1.5  # Seconds to show selection before resetting


class FmdLocationSourceSelect(SelectEntity):
    """Select entity for choosing location source provider."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:map-marker-multiple"
    _attr_options = [
        "All Providers (Default)",
        "GPS Only (Accurate)",
        "Cell Only (Fast)",
        "Last Known (No Request)",
    ]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_location_source"
        self._attr_name = "Location source"
        # Restore from config entry or default to "All Providers"
        self._attr_current_option = entry.data.get(
            "location_source_current_option", "All Providers (Default)"
        )

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_select_option(self, option: str) -> None:
        """Handle location source selection and persist state."""
        _LOGGER.info("Location source changed to: {option}")
        self._attr_current_option = option
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["location_source_current_option"] = option
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

    def get_provider_value(self) -> str:
        """Convert the selected option to the API provider parameter.

        Returns:
            str: Provider value for request_location() - "all", "gps", "cell", or "last"
        """
        provider_map = {
            "All Providers (Default)": "all",
            "GPS Only (Accurate)": "gps",
            "Cell Only (Fast)": "cell",
            "Last Known (No Request)": "last",
        }
        return provider_map.get(self._attr_current_option, "all")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FMD select entities."""
    async_add_entities(
        [
            FmdLocationSourceSelect(hass, entry),
            FmdBluetoothSelect(hass, entry),
            FmdDoNotDisturbSelect(hass, entry),
            FmdRingerModeSelect(hass, entry),
        ]
    )


class FmdBluetoothSelect(SelectEntity):
    """Select entity for Bluetooth commands."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bluetooth"
    _attr_options = [COMMAND_PLACEHOLDER, "Enable Bluetooth", "Disable Bluetooth"]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_bluetooth_command"
        self._attr_name = "Bluetooth"
        self._attr_current_option = COMMAND_PLACEHOLDER

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        if option == COMMAND_PLACEHOLDER:
            return  # No action for placeholder

        # Get tracker API
        tracker = self._entry.runtime_data.tracker
        if not tracker:
            _LOGGER.error("Could not find tracker to send Bluetooth command")
            return

        try:
            if option == "Enable Bluetooth":
                await tracker.api.set_bluetooth(True)
                _LOGGER.info("Sent Bluetooth enable command to device")
            elif option == "Disable Bluetooth":
                await tracker.api.set_bluetooth(False)
                _LOGGER.info("Sent Bluetooth disable command to device")

            # Update state to show selection temporarily
            self._attr_current_option = option
            self.async_write_ha_state()

            # Brief pause to show selection
            await asyncio.sleep(RESET_DELAY)

        except Exception:
            _LOGGER.exception("Failed to send Bluetooth command")
        finally:
            # Always reset to placeholder
            self._attr_current_option = COMMAND_PLACEHOLDER
            self.async_write_ha_state()


class FmdDoNotDisturbSelect(SelectEntity):
    """Select entity for Do Not Disturb commands."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:bell-off-outline"
    _attr_options = [
        COMMAND_PLACEHOLDER,
        "Enable Do Not Disturb",
        "Disable Do Not Disturb",
    ]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_dnd_command"
        self._attr_name = "Volume: Do Not Disturb"
        self._attr_current_option = COMMAND_PLACEHOLDER

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        if option == COMMAND_PLACEHOLDER:
            return  # No action for placeholder

        # Get tracker API
        tracker = self._entry.runtime_data.tracker
        if not tracker:
            _LOGGER.error("Could not find tracker to send DND command")
            return

        try:
            if option == "Enable Do Not Disturb":
                await tracker.api.set_do_not_disturb(True)
                _LOGGER.info("Sent DND enable command to device")
            elif option == "Disable Do Not Disturb":
                await tracker.api.set_do_not_disturb(False)
                _LOGGER.info("Sent DND disable command to device")

            # Update state to show selection temporarily
            self._attr_current_option = option
            self.async_write_ha_state()

            # Brief pause to show selection
            await asyncio.sleep(RESET_DELAY)

        except Exception:
            _LOGGER.exception("Failed to send DND command")
        finally:
            # Always reset to placeholder
            self._attr_current_option = COMMAND_PLACEHOLDER
            self.async_write_ha_state()


class FmdRingerModeSelect(SelectEntity):
    """Select entity for Ringer Mode commands."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:volume-high"
    _attr_options = [
        COMMAND_PLACEHOLDER,
        "Normal (Sound + Vibrate)",
        "Vibrate Only",
        "Silent",
    ]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the select entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ringer_mode_command"
        self._attr_name = "Volume: Ringer mode"
        self._attr_current_option = COMMAND_PLACEHOLDER

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_select_option(self, option: str) -> None:
        """Handle option selection."""
        if option == COMMAND_PLACEHOLDER:
            return  # No action for placeholder

        # Get tracker API
        tracker = self._entry.runtime_data.tracker
        if not tracker:
            _LOGGER.error("Could not find tracker to send ringer mode command")
            return

        try:
            if option == "Normal (Sound + Vibrate)":
                await tracker.api.set_ringer_mode("normal")
                _LOGGER.info("Sent ringer mode 'normal' command to device")
            elif option == "Vibrate Only":
                await tracker.api.set_ringer_mode("vibrate")
                _LOGGER.info("Sent ringer mode 'vibrate' command to device")
            elif option == "Silent":
                await tracker.api.set_ringer_mode("silent")
                _LOGGER.info("Sent ringer mode 'silent' command to device")

            # Update state to show selection temporarily
            self._attr_current_option = option
            self.async_write_ha_state()

            # Brief pause to show selection
            await asyncio.sleep(RESET_DELAY)

        except Exception:
            _LOGGER.exception("Failed to send ringer mode command")
        finally:
            # Always reset to placeholder
            self._attr_current_option = COMMAND_PLACEHOLDER
            self.async_write_ha_state()
