"""The EPH Controls Ember integration."""

from dataclasses import dataclass
from typing import Any

from pyephember2.pyephember2 import EphEmber, EphEmberError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import LOGGER, PLATFORMS, signal_zone_update


@dataclass
class EphEmberData:
    """Ember client and the homes (with their zones) found at setup."""

    ember: EphEmber
    homes: list[dict[str, Any]]


type EphEmberConfigEntry = ConfigEntry[EphEmberData]


async def async_setup_entry(hass: HomeAssistant, entry: EphEmberConfigEntry) -> None:
    """Set up EPH Controls Ember from a config entry."""
    try:
        ember = await hass.async_add_executor_job(
            EphEmber, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except EphEmberError as err:
        raise ConfigEntryNotReady(f"Cannot connect to EPH Ember: {err}") from err
    except RuntimeError as err:
        raise ConfigEntryError("Invalid username or password") from err

    try:
        homes = await hass.async_add_executor_job(ember.get_zones)
    except RuntimeError as err:
        raise ConfigEntryNotReady(f"Cannot get zones from EPH Ember: {err}") from err

    entry.runtime_data = EphEmberData(ember, homes)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def zone_updated(zone: dict[str, Any]) -> None:
        """Pass a live update from the listener thread to the zone's entity."""
        dispatcher_send(hass, signal_zone_update(entry.entry_id, zone["zoneid"]), zone)

    try:
        await hass.async_add_executor_job(ember.start_listening, zone_updated)
    except RuntimeError as err:
        LOGGER.warning("No live updates from EPH Ember, polling only: %s", err)
        return

    async def stop_listening(_: Event | None = None) -> None:
        await hass.async_add_executor_job(ember.stop_listening)

    entry.async_on_unload(stop_listening)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_listening)
    )


async def async_unload_entry(hass: HomeAssistant, entry: EphEmberConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
