"""The BT Home Hub 5 integration."""

from collections.abc import Collection
from datetime import timedelta

from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_LEGACY_KNOWN_DEVICES, PLATFORMS
from .coordinator import BTHomeHub5ConfigEntry, BTHomeHub5DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: BTHomeHub5ConfigEntry) -> None:
    """Set up BT Home Hub 5 from a config entry."""
    coordinator = BTHomeHub5DataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    seen_macs = set(coordinator.data)

    @callback
    def async_check_new_devices() -> None:
        """Check conflicts when a new device appears."""
        if not coordinator.data.keys() - seen_macs:
            return
        seen_macs.update(coordinator.data)
        entry.async_create_background_task(
            hass,
            _async_check_legacy_known_devices(hass, entry, set(seen_macs)),
            name=f"{DOMAIN} legacy known_devices check",
        )

    await _async_check_legacy_known_devices(hass, entry, seen_macs)
    entry.async_on_unload(coordinator.async_add_listener(async_check_new_devices))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def _legacy_issue_id(entry: BTHomeHub5ConfigEntry) -> str:
    """Return the legacy conflict issue ID for this router."""
    return f"{ISSUE_LEGACY_KNOWN_DEVICES}_{entry.entry_id}"


async def _async_check_legacy_known_devices(
    hass: HomeAssistant, entry: BTHomeHub5ConfigEntry, tracked: Collection[str]
) -> None:
    """Report legacy trackers which conflict with newly registered entities."""
    legacy_devices = await async_load_config(
        hass.config.path(YAML_DEVICES), hass, timedelta(0)
    )
    macs = {mac.upper() for mac in tracked}
    conflicting = sorted(
        device.dev_id
        for device in legacy_devices
        if device.track and device.mac in macs
    )

    if not conflicting:
        ir.async_delete_issue(hass, DOMAIN, _legacy_issue_id(entry))
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        _legacy_issue_id(entry),
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_LEGACY_KNOWN_DEVICES,
        translation_placeholders={
            "host": entry.data[CONF_HOST],
            "path": YAML_DEVICES,
            "devices": "\n".join(f"- `{dev_id}`" for dev_id in conflicting),
        },
    )


async def async_unload_entry(hass: HomeAssistant, entry: BTHomeHub5ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
