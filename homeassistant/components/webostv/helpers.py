"""Helper functions for LG webOS TV."""

from __future__ import annotations

import logging

from aiowebostv import WebOsClient, WebOsTvState

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, LIVE_TV_APP_ID

_LOGGER = logging.getLogger(__name__)

type WebOsTvConfigEntry = ConfigEntry[WebOsClient]


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


@callback
def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises HomeAssistantError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if (
        entity_entry is None
        or entity_entry.device_id is None
        or entity_entry.platform != DOMAIN
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity_id",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity_entry.device_id


@callback
def async_get_client_by_device_entry(
    hass: HomeAssistant, device: DeviceEntry
) -> WebOsClient:
    """Get WebOsClient from Device Registry by device entry.

    Raises ValueError if client is not found.
    """
    for config_entry_id in device.config_entries:
        entry: WebOsTvConfigEntry | None = hass.config_entries.async_get_entry(
            config_entry_id
        )
        if entry and entry.domain == DOMAIN:
            if entry.state is ConfigEntryState.LOADED:
                return entry.runtime_data

            raise ValueError(
                f"Device {device.id} is not from a loaded {DOMAIN} config entry"
            )

    raise ValueError(
        f"Device {device.id} is not from an existing {DOMAIN} config entry"
    )


def get_sources(tv_state: WebOsTvState) -> list[str]:
    """Construct sources list."""
    sources = []
    found_live_tv = False
    for app in tv_state.apps.values():
        sources.append(app["title"])
        if app["id"] == LIVE_TV_APP_ID:
            found_live_tv = True

    for source in tv_state.inputs.values():
        sources.append(source["label"])
        if source["appId"] == LIVE_TV_APP_ID:
            found_live_tv = True

    if not found_live_tv:
        sources.append("Live TV")

    # Preserve order when filtering duplicates
    return list(dict.fromkeys(sources))


def update_client_key(hass: HomeAssistant, entry: WebOsTvConfigEntry) -> None:
    """Check and update stored client key if key has changed."""
    client: WebOsClient = entry.runtime_data
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_CLIENT_SECRET]

    if client.client_key != key:
        _LOGGER.debug("Updating client key for host %s", host)
        data = {CONF_HOST: host, CONF_CLIENT_SECRET: client.client_key}
        hass.config_entries.async_update_entry(entry, data=data)
