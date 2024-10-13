"""Support for HomematicIP Cloud devices."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from .hap import HomematicipHAP
from .services import async_setup_services, async_unload_services

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=""): vol.Any(cv.string),
                        vol.Required(CONF_ACCESSPOINT): cv.string,
                        vol.Required(CONF_AUTHTOKEN): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomematicIP Cloud component."""
    hass.data[DOMAIN] = {}

    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in {
            entry.data[HMIPC_HAPID]
            for entry in hass.config_entries.async_entries(DOMAIN)
        }:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={
                        HMIPC_HAPID: conf[CONF_ACCESSPOINT],
                        HMIPC_AUTHTOKEN: conf[CONF_AUTHTOKEN],
                        HMIPC_NAME: conf[CONF_NAME],
                    },
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an access point from a config entry."""

    # 0.104 introduced config entry unique id, this makes upgrading possible
    if entry.unique_id is None:
        new_data = dict(entry.data)

        hass.config_entries.async_update_entry(
            entry, unique_id=new_data[HMIPC_HAPID], data=new_data
        )

    hap = HomematicipHAP(hass, entry)
    hass.data[DOMAIN][entry.unique_id] = hap

    if not await hap.async_setup():
        return False

    await async_setup_services(hass)
    _async_remove_obsolete_entities(hass, entry, hap)

    # Register on HA stop event to gracefully shutdown HomematicIP Cloud connection
    hap.reset_connection_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, hap.shutdown
    )

    # Register hap as device in registry.
    device_registry = dr.async_get(hass)

    home = hap.home
    hapname = home.label if home.label != entry.unique_id else f"Home-{home.label}"

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, home.id)},
        manufacturer="eQ-3",
        # Add the name from config entry.
        name=hapname,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hap = hass.data[DOMAIN].pop(entry.unique_id)
    hap.reset_connection_listener()

    await async_unload_services(hass)

    return await hap.async_reset()


@callback
def _async_remove_obsolete_entities(
    hass: HomeAssistant, entry: ConfigEntry, hap: HomematicipHAP
):
    """Remove obsolete entities from entity registry."""

    if hap.home.currentAPVersion < "2.2.12":
        return

    entity_registry = er.async_get(hass)
    er_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    for er_entry in er_entries:
        if er_entry.unique_id.startswith("HomematicipAccesspointStatus"):
            entity_registry.async_remove(er_entry.entity_id)
            continue

        for hapid in hap.home.accessPointUpdateStates:
            if er_entry.unique_id == f"HomematicipBatterySensor_{hapid}":
                entity_registry.async_remove(er_entry.entity_id)
