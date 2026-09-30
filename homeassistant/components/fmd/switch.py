"""Switch entities for FMD integration."""

import asyncio
import contextlib
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

WIPE_SAFETY_TIMEOUT = 60  # Seconds before safety switch auto-disables


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FMD switch entities."""
    switches = [
        FmdHighFrequencyModeSwitch(hass, entry),
        FmdAllowInaccurateSwitch(hass, entry),
        FmdPhotoAutoCleanupSwitch(hass, entry),
        FmdWipeSafetySwitch(hass, entry),
    ]

    async_add_entities(switches)

    # Store switch references for other platforms to access
    for switch in switches:
        if isinstance(switch, FmdPhotoAutoCleanupSwitch):
            entry.runtime_data.photo_auto_cleanup_switch = switch
        if isinstance(switch, FmdWipeSafetySwitch):
            entry.runtime_data.wipe_safety_switch = switch


class FmdHighFrequencyModeSwitch(SwitchEntity):
    """Switch entity to enable high-frequency update mode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the switch entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_high_frequency_mode"
        self._attr_name = "High frequency mode"
        self._attr_is_on = entry.data.get("high_frequency_mode_is_on", False)
        self._attr_icon = "mdi:run-fast"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on high-frequency mode and persist state."""
        _LOGGER.info("High frequency mode enabled")
        self._attr_is_on = True
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["high_frequency_mode_is_on"] = True
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Enable high-frequency mode in the tracker
        tracker = self._entry.runtime_data.tracker
        if tracker:
            await tracker.set_high_frequency_mode(True)
            _LOGGER.info("High-frequency mode activated in tracker")
        else:
            _LOGGER.error("Could not find tracker to enable high-frequency mode")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off high-frequency mode and persist state."""
        _LOGGER.info("High frequency mode disabled")
        self._attr_is_on = False
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["high_frequency_mode_is_on"] = False
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Disable high-frequency mode in the tracker
        tracker = self._entry.runtime_data.tracker
        if tracker:
            await tracker.set_high_frequency_mode(False)
            _LOGGER.info("High-frequency mode deactivated in tracker")
        else:
            _LOGGER.error("Could not find tracker to disable high-frequency mode")


class FmdAllowInaccurateSwitch(SwitchEntity):
    """Switch entity to allow inaccurate location updates."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:map-marker-question"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the switch entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_allow_inaccurate"
        self._attr_name = "Location: allow inaccurate updates"
        self._attr_is_on = entry.data.get(
            "location_allow_inaccurate_is_on",
            entry.data.get(
                "allow_inaccurate_locations",
                not entry.data.get("block_inaccurate", True),
            ),
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allow inaccurate location updates and persist state."""
        _LOGGER.info("Inaccurate locations allowed (blocking disabled)")
        self._attr_is_on = True
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["location_allow_inaccurate_is_on"] = True
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Update the tracker to disable filtering
        tracker = self._entry.runtime_data.tracker
        if tracker:
            tracker.block_inaccurate = False
            _LOGGER.info("Location accuracy filtering disabled in tracker")
        else:
            _LOGGER.error("Could not find tracker to update filtering setting")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disallow inaccurate location updates and persist state."""
        _LOGGER.info("Inaccurate locations disallowed (blocking enabled)")
        self._attr_is_on = False
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["location_allow_inaccurate_is_on"] = False
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        # Update the tracker to enable filtering
        tracker = self._entry.runtime_data.tracker
        if tracker:
            tracker.block_inaccurate = True
            _LOGGER.info("Location accuracy filtering enabled in tracker")
        else:
            _LOGGER.error("Could not find tracker to update filtering setting")


class FmdWipeSafetySwitch(SwitchEntity):
    """Safety switch that must be enabled before device wipe can be performed.

    This switch automatically disables itself after 60 seconds for safety.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:alert-octagon"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the safety switch entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_wipe_safety"
        self._attr_name = "Wipe: ⚠️ Safety switch ⚠️"
        self._attr_is_on = False
        self._auto_disable_task: asyncio.Task[None] | None = None

        # Store reference for the wipe button to access
        entry.runtime_data.wipe_safety_switch = self

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the auto-disable task when entity is removed."""
        if self._auto_disable_task:
            self._auto_disable_task.cancel()
            self._auto_disable_task = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable device wipe safety (allows wipe button to work)."""
        _LOGGER.critical("🚨🚨🚨 DEVICE WIPE SAFETY ENABLED 🚨🚨🚨")
        _LOGGER.critical(
            "⚠️ The 'Wipe Device' button is now ACTIVE for the next 60 seconds!"
        )
        _LOGGER.critical(
            "⚠️ Pressing the wipe button will PERMANENTLY ERASE ALL DATA on your device!"
        )
        _LOGGER.critical("⚠️ To CANCEL: Turn this safety switch OFF immediately!")
        _LOGGER.critical("⏰ This safety will AUTO-DISABLE in 60 seconds")
        self._attr_is_on = True
        self.async_write_ha_state()

        # Cancel any existing auto-disable task
        if self._auto_disable_task:
            self._auto_disable_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._auto_disable_task

        # Schedule automatic disable after 60 seconds (avoid duplicate tasks)
        self._auto_disable_task = asyncio.create_task(self._auto_disable())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable device wipe safety (blocks wipe button)."""
        _LOGGER.warning("✅ DEVICE WIPE SAFETY DISABLED - Wipe button is now BLOCKED")
        _LOGGER.info(
            "Device wipe command is no longer available until safety is re-enabled"
        )
        self._attr_is_on = False
        self.async_write_ha_state()

        # Cancel auto-disable task if running
        if self._auto_disable_task:
            self._auto_disable_task.cancel()
            self._auto_disable_task = None

    async def _auto_disable(self) -> None:
        """Automatically disable the safety switch after timeout."""
        try:
            await asyncio.sleep(WIPE_SAFETY_TIMEOUT)
            _LOGGER.warning("⏰ DEVICE WIPE SAFETY AUTO-DISABLED after 60 seconds")
            _LOGGER.info("Wipe button is now blocked - safety timeout expired")
            self._attr_is_on = False
            self.async_write_ha_state()
            self._auto_disable_task = None
        except asyncio.CancelledError:
            # Task was cancelled; auto-disable is moot
            return


class FmdPhotoAutoCleanupSwitch(SwitchEntity):
    """Switch entity to enable automatic cleanup of old photos.

    When enabled, automatically deletes oldest photos after download
    if total count exceeds the "Photo: Max to retain" limit.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:delete-sweep"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the photo auto-cleanup switch entity."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_photo_auto_cleanup"
        self._attr_name = "Photo: Auto-cleanup"
        self._attr_is_on = entry.data.get("photo_auto_cleanup_is_on", False)

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"FMD {self._entry.data['id']}",
            "manufacturer": "FMD",
            "model": "Device Tracker",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable automatic photo cleanup and persist state."""
        _LOGGER.info(
            "Photo auto-cleanup ENABLED - Old photos will be deleted when limit exceeded"
        )
        _LOGGER.info(
            "Maximum photos retained: Set via 'Photo: Max to retain' number entity"
        )
        self._attr_is_on = True
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["photo_auto_cleanup_is_on"] = True
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable automatic photo cleanup and persist state."""
        _LOGGER.info(
            "Photo auto-cleanup DISABLED - Photos will not be automatically deleted"
        )
        self._attr_is_on = False
        self.async_write_ha_state()

        # Persist to config entry
        new_data = dict(self._entry.data)
        new_data["photo_auto_cleanup_is_on"] = False
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)
