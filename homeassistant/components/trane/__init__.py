"""Integration for Trane Local thermostats."""

from __future__ import annotations

from steamloop import (
    AuthenticationError,
    SteamloopConnectionError,
    ThermostatConnection,
)

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_SECRET_KEY, DOMAIN, MANUFACTURER, PLATFORMS
from .types import TraneConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: TraneConfigEntry) -> bool:
    """Set up Trane Local from a config entry."""
    conn = ThermostatConnection(
        entry.data[CONF_HOST],
        secret_key=entry.data[CONF_SECRET_KEY],
    )

    try:
        await conn.connect()
        await conn.login()
    except (SteamloopConnectionError, TimeoutError) as err:
        await conn.disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err
    except AuthenticationError as err:
        await conn.disconnect()
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
        ) from err

    conn.start_background_tasks()
    entry.runtime_data = conn

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        translation_key="thermostat",
        translation_placeholders={"host": entry.data[CONF_HOST]},
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TraneConfigEntry) -> bool:
    """Unload a Trane Local config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.disconnect()
    return unload_ok
