"""Component to integrate Kingspan Watchman SENSiT with Home Assistant."""

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN, PLATFORMS
from .coordinator import SENSiTConfigEntry, SENSiTDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


@callback
def _async_create_repair_issue(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Create a repair issue for an entry that cannot authenticate."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"credentials_{config_entry.entry_id}",
        is_fixable=True,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="auth_failed",
        translation_placeholders={"title": config_entry.title},
    )


@callback
def _async_delete_repair_issue(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Delete the repair issue for a config entry when it has been fixed."""
    ir.async_delete_issue(hass, DOMAIN, f"credentials_{config_entry.entry_id}")


async def async_setup_entry(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Set up this integration using UI."""
    username = config_entry.data.get(CONF_USERNAME)
    password = config_entry.data.get(CONF_PASSWORD)

    if not username or not password:
        _async_create_repair_issue(hass, config_entry)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="credentials_not_set",
        )

    coordinator = SENSiTDataUpdateCoordinator(
        hass,
        config_entry=config_entry,
        httpx_client=get_async_client(hass),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        _async_create_repair_issue(hass, config_entry)
        raise

    if not coordinator.data:
        _async_delete_repair_issue(hass, config_entry)
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="no_data")

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    _async_delete_repair_issue(hass, config_entry)
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))


async def async_unload_entry(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Handle removal of an entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
    _async_delete_repair_issue(hass, config_entry)


async def async_reload_entry(
    hass: HomeAssistant, config_entry: SENSiTConfigEntry
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    _hass: HomeAssistant,
    config_entry: SENSiTConfigEntry,
    device_entry: dr.AnyDeviceEntry,
) -> bool:
    """Allow manual removal of stale devices via the UI."""
    coordinator = config_entry.runtime_data
    active_serials = {tank.serial_number for tank in coordinator.data}

    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN and identifier[1] in active_serials:
            return False

    return True
