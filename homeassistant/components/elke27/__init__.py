"""Set up the Elke27 integration."""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path

_VENDOR_PATH = Path(__file__).resolve().parent / "vendor" / "elkm1"
if _VENDOR_PATH.exists() and str(_VENDOR_PATH) not in sys.path:
    sys.path.insert(0, str(_VENDOR_PATH))

from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    CONF_PANEL,
    CONF_PIN,
    DATA_COORDINATOR,
    DATA_HUB,
    DOMAIN,
)
from .coordinator import Elke27DataUpdateCoordinator
from .entity import unique_base
from .hub import Elke27Hub
from .identity import async_get_integration_serial

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys_json = entry.data.get(CONF_LINK_KEYS_JSON)
    pin = entry.data.get(CONF_PIN)
    panel_name = _panel_name_from_entry(entry.data.get(CONF_PANEL))
    if not link_keys_json:
        raise ConfigEntryAuthFailed("Link keys are missing; relink required")
    integration_serial = entry.data.get(CONF_INTEGRATION_SERIAL)
    if not integration_serial:
        integration_serial = await async_get_integration_serial(hass, host)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_INTEGRATION_SERIAL: integration_serial},
        )
    if panel_name:
        _LOGGER.debug("Discovered panel name: %s", panel_name)
    hub = Elke27Hub(
        hass,
        host,
        port,
        link_keys_json,
        integration_serial,
        pin,
        panel_name,
    )
    try:
        await hub.async_connect()
    except Elke27LinkRequiredError as err:
        raise ConfigEntryAuthFailed(
            "Linking credentials are invalid; relink required"
        ) from err
    except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError) as err:
        _LOGGER.exception("Failed to set up connection to %s:%s", host, port)
        with contextlib.suppress(Exception):
            await hub.async_disconnect()
        raise ConfigEntryNotReady(
            "The client did not become ready; check host and port"
        ) from err

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    await coordinator.async_start()
    await coordinator.async_refresh_now()
    await _async_migrate_unique_ids(hass, entry, unique_base(hub, coordinator, entry))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_HUB: hub,
        DATA_COORDINATOR: coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data is not None:
        coordinator: Elke27DataUpdateCoordinator | None = data.get(DATA_COORDINATOR)
        hub: Elke27Hub | None = data.get(DATA_HUB)
        if coordinator is not None:
            await coordinator.async_stop()
        if hub is not None:
            await hub.async_disconnect()
    return unload_ok


def _panel_name_from_entry(panel: object | None) -> str | None:
    if isinstance(panel, dict):
        return panel.get("panel_name") or panel.get("name")
    return None


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, base: str
) -> None:
    """Migrate legacy unique IDs to the <base>:<domain>:<id> format."""
    registry = er.async_get(hass)
    prefix = f"{base}_"
    for entity in registry.entities.values():
        if entity.platform != DOMAIN:
            continue
        if entity.config_entry_id != entry.entry_id:
            continue
        unique_id = entity.unique_id
        if not unique_id.startswith(prefix):
            continue
        rest = unique_id[len(prefix) :]
        if "_" not in rest:
            continue
        domain, numeric_id = rest.rsplit("_", 1)
        new_unique_id = f"{base}:{domain}:{numeric_id}"
        if registry.async_get_entity_id(entity.domain, DOMAIN, new_unique_id):
            _LOGGER.debug(
                "Unique ID migration skipped for %s; %s already exists",
                entity.entity_id,
                new_unique_id,
            )
            continue
        registry.async_update_entity(entity.entity_id, new_unique_id=new_unique_id)
