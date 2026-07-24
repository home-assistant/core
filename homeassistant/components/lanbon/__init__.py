"""LANBON integration setup."""
from __future__ import annotations

from dataclasses import dataclass
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import CONF_TOKEN, DOMAIN, SERVICE_SET_CHANNEL_NAME
from .coordinator import LanbonApi, LanbonCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.LIGHT, Platform.COVER]

SERVICE_SET_CHANNEL_NAME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required("name"): cv.string,
    }
)


@dataclass
class LanbonRuntimeData:
    """Runtime objects for one config entry."""

    api: LanbonApi
    coordinator: LanbonCoordinator


type LanbonConfigEntry = ConfigEntry[LanbonRuntimeData]


def _find_switch(hass: HomeAssistant, entity_id: str):
    for platform in async_get_platforms(hass, DOMAIN):
        if platform.domain != "switch":
            continue
        ent = platform.entities.get(entity_id)
        if ent is not None:
            return ent
    return None


async def async_setup_entry(hass: HomeAssistant, entry: LanbonConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 8765)
    token = entry.data[CONF_TOKEN]
    api = LanbonApi(hass, host, port, token)
    coordinator = LanbonCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LanbonRuntimeData(api=api, coordinator=coordinator)

    host_mac = (entry.data.get("mac") or "").upper()
    data = coordinator.data or {}
    host_info = data.get("host") or {}
    if not host_mac:
        host_mac = str(host_info.get("mac") or host).upper()

    registry = dr.async_get(hass)
    hub = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, host_mac)},
        manufacturer="LANBON",
        name=host_info.get("name") or f"LANBON {host_mac[-4:]}",
        model=str(host_info.get("kind") or "host"),
    )

    for dev in data.get("devices") or []:
        mac = str(dev.get("mac") or "").upper()
        if not mac or mac == host_mac:
            continue
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, mac)},
            manufacturer="LANBON",
            name=dev.get("name") or f"LANBON {mac[-4:]}",
            model=str(dev.get("kind") or "node"),
            via_device=hub.id,
        )

    await api.async_start_ws(coordinator.handle_ws)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_set_channel_name(call: ServiceCall) -> None:
        name = str(call.data["name"]).strip()
        for entity_id in call.data[ATTR_ENTITY_ID]:
            ent = _find_switch(hass, entity_id)
            if ent is None:
                _LOGGER.warning("set_channel_name: %s not a LANBON switch", entity_id)
                continue
            await ent.async_set_channel_name(name)

    # action-setup: register once; remove when last entry unloads
    if not hass.services.has_service(DOMAIN, SERVICE_SET_CHANNEL_NAME):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CHANNEL_NAME,
            async_set_channel_name,
            schema=SERVICE_SET_CHANNEL_NAME_SCHEMA,
        )

    @callback
    def _on_entity_registry_updated(event) -> None:
        """HA UI rename → push name_set to host panel."""
        if event.data.get("action") != "update":
            return
        changes = event.data.get("changes") or {}
        if "name" not in changes:
            return
        entity_id = event.data.get("entity_id")
        if not entity_id or not str(entity_id).startswith("switch."):
            return
        ent = _find_switch(hass, entity_id)
        if ent is None:
            return
        if getattr(ent, "_suppress_registry_push", False):
            return
        ereg = er.async_get(hass)
        entry_er = ereg.async_get(entity_id)
        if entry_er is None or entry_er.name is None:
            return
        new_name = str(entry_er.name).strip()
        if not new_name or new_name == ent._attr_name:
            return

        async def _push() -> None:
            try:
                await ent.async_set_channel_name(new_name)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Failed to push rename for %s", entity_id)

        hass.async_create_task(_push())

    entry.async_on_unload(
        hass.bus.async_listen(_EVENT_ENTITY_REGISTRY_UPDATED, _on_entity_registry_updated)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LanbonConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    await entry.runtime_data.api.async_stop_ws()
    if (
        not any(
            e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
            for e in hass.config_entries.async_entries(DOMAIN)
        )
        and hass.services.has_service(DOMAIN, SERVICE_SET_CHANNEL_NAME)
    ):
        hass.services.async_remove(DOMAIN, SERVICE_SET_CHANNEL_NAME)
    return True
