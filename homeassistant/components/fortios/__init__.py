"""Set up FortiOS from a config entry."""

from collections.abc import Collection
from datetime import timedelta
from functools import partial

from aiofortiosapi import FortiOSAuthenticationError, FortiOSError

from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .client import FortiOSClient, UnsupportedVersion
from .const import DOMAIN
from .coordinator import FortiOSConfigEntry, FortiOSCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: FortiOSConfigEntry) -> bool:
    """Set up FortiOS and its shared coordinator."""
    try:
        client = FortiOSClient(hass, dict(entry.data))
        await client.connect()
    except FortiOSAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except (FortiOSError, UnsupportedVersion) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    coordinator = FortiOSCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    seen_macs = set(coordinator.data)

    @callback
    def async_check_new_devices() -> None:
        """Check legacy conflicts for clients first reported after setup."""
        if not coordinator.data.keys() - seen_macs:
            return
        seen_macs.update(coordinator.data)
        entry.async_create_background_task(
            hass,
            _async_check_legacy_known_devices(hass, entry, set(seen_macs)),
            name="FortiOS legacy known_devices check",
        )

    await _async_check_legacy_known_devices(hass, entry, seen_macs)
    entry.async_on_unload(coordinator.async_add_listener(async_check_new_devices))
    entry.async_on_unload(
        partial(
            ir.async_delete_issue,
            hass,
            DOMAIN,
            f"legacy_known_devices_{entry.entry_id}",
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FortiOSConfigEntry) -> bool:
    """Unload the tracker platform."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    return True


async def _async_check_legacy_known_devices(
    hass: HomeAssistant, entry: FortiOSConfigEntry, tracked: Collection[str]
) -> None:
    """Report legacy trackers that can claim the new entities' IDs."""
    devices = await async_load_config(
        hass.config.path(YAML_DEVICES), hass, timedelta(0)
    )
    macs = {mac.upper() for mac in tracked}
    conflicting = sorted(
        device.dev_id for device in devices if device.track and device.mac in macs
    )
    issue_id = f"legacy_known_devices_{entry.entry_id}"
    if not conflicting:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="legacy_known_devices",
        translation_placeholders={
            "host": entry.data[CONF_HOST],
            "path": YAML_DEVICES,
            "devices": "\n".join(f"- `{dev_id}`" for dev_id in conflicting),
        },
    )
