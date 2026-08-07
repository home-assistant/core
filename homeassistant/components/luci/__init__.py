"""The luci component."""

from collections.abc import Collection
from datetime import timedelta

from openwrt_luci_rpc import OpenWrtRpc
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.device_tracker.legacy import (
    YAML_DEVICES,
    async_load_config,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir

from .const import (
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    ISSUE_LEGACY_KNOWN_DEVICES,
    PLATFORMS,
)
from .coordinator import LuciConfigEntry, LuciCoordinator


def _connect(
    host: str, username: str, password: str, ssl: bool, verify_ssl: bool
) -> OpenWrtRpc:
    """Connect to the router and verify login."""
    router = OpenWrtRpc(host, username, password, ssl, verify_ssl)
    if not router.is_logged_in():
        raise ConfigEntryAuthFailed("Invalid credentials for router")
    return router


async def async_setup_entry(hass: HomeAssistant, entry: LuciConfigEntry) -> bool:
    """Set up OpenWrt (luci) from a config entry."""
    try:
        router = await hass.async_add_executor_job(
            _connect,
            entry.data[CONF_HOST],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_SSL, DEFAULT_SSL),
            entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
    except (ConnectionError, RequestsConnectionError) as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to router at {entry.data[CONF_HOST]}"
        ) from err

    coordinator = LuciCoordinator(hass, entry, router)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    seen_macs = set(coordinator.data)

    @callback
    def _async_check_new_devices() -> None:
        """Re-check conflicts when the router reports a MAC we haven't seen."""
        if not coordinator.data.keys() - seen_macs:
            return
        seen_macs.update(coordinator.data)
        entry.async_create_task(
            hass, _async_check_legacy_known_devices(hass, set(seen_macs))
        )

    await _async_check_legacy_known_devices(hass, seen_macs)
    entry.async_on_unload(coordinator.async_add_listener(_async_check_new_devices))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_check_legacy_known_devices(
    hass: HomeAssistant, tracked: Collection[str]
) -> None:
    """Report leftover known_devices.yaml entries for devices we now track.

    Legacy trackers are not in the entity registry, so they silently claim the
    entity IDs our entities are registered under and those entities get dropped.
    """
    legacy_devices = await async_load_config(
        hass.config.path(YAML_DEVICES), hass, timedelta(0)
    )
    # async_load_config upper cases the MAC addresses it reads.
    macs = {mac.upper() for mac in tracked}
    conflicting = sorted(
        device.dev_id
        for device in legacy_devices
        if device.track and device.mac in macs
    )

    if not conflicting:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_LEGACY_KNOWN_DEVICES)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_LEGACY_KNOWN_DEVICES,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEGACY_KNOWN_DEVICES,
        translation_placeholders={
            "path": YAML_DEVICES,
            "devices": "\n".join(f"- `{dev_id}`" for dev_id in conflicting),
        },
    )


async def async_unload_entry(hass: HomeAssistant, entry: LuciConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
