"""Set up the Elke27 integration."""

import contextlib
import logging
from typing import TYPE_CHECKING

from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27TimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CONF_INTEGRATION_SERIAL, CONF_LEGACY_PIN, CONF_LINK_KEYS_JSON, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .entity import unique_base
from .hub import Elke27Hub
from .identity import async_get_integration_serial
from .models import Elke27RuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
]


async def async_setup(_hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up the Elke27 integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    link_keys_json = entry.data.get(CONF_LINK_KEYS_JSON)
    if not link_keys_json:
        msg = "Link keys are missing"
        raise ConfigEntryError(msg)
    integration_serial = entry.data.get(CONF_INTEGRATION_SERIAL)
    entry_data = dict(entry.data)
    pin_removed = entry_data.pop(CONF_LEGACY_PIN, None)
    if not integration_serial:
        integration_serial = await async_get_integration_serial(hass, host)
        entry_data[CONF_INTEGRATION_SERIAL] = integration_serial
        hass.config_entries.async_update_entry(entry, data=entry_data)
    elif pin_removed is not None:
        hass.config_entries.async_update_entry(entry, data=entry_data)
    hub = Elke27Hub(
        hass,
        host,
        port,
        link_keys_json,
        integration_serial,
        None,
    )
    try:
        await hub.async_connect()
    except Elke27LinkRequiredError as err:
        msg = "Linking credentials are invalid"
        raise ConfigEntryError(msg) from err
    except (Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError) as err:
        _LOGGER.exception("Failed to set up connection to %s:%s", host, port)
        with contextlib.suppress(Exception):
            await hub.async_disconnect()
        msg = "The client did not become ready; check host and port"
        raise ConfigEntryNotReady(msg) from err

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    await coordinator.async_start()
    await coordinator.async_refresh_now()

    await _async_migrate_unique_ids(hass, entry, unique_base(hub, coordinator, entry))
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data: Elke27RuntimeData | None = getattr(entry, "runtime_data", None)
    if unload_ok and data is not None:
        await data.coordinator.async_stop()
        await data.hub.async_disconnect()
    return unload_ok


async def _async_migrate_unique_ids(
    hass: HomeAssistant, entry: ConfigEntry, base: str
) -> None:
    """Migrate legacy unique IDs to the <base>:<domain>:<id> format."""
    registry = er.async_get(hass)
    prefix = f"{base}_"
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.platform != DOMAIN:
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
