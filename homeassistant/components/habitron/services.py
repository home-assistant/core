"""Service registration for the Habitron integration."""

from collections.abc import Callable, Coroutine
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    DOMAIN,
    EVNT_ARG1,
    EVNT_ARG2,
    EVNT_ARG3,
    EVNT_ARG4,
    EVNT_ARG5,
    EVNT_TYPE,
    HUB_UID,
    MOD_NMBR,
    RESTART_ALL,
    ROUTER_NMBR,
)

if TYPE_CHECKING:
    from .smart_hub import SmartHub

_LOGGER = logging.getLogger(__name__)

SERVICE_HUB_RESTART = "hub_restart"
SERVICE_HUB_REBOOT = "hub_reboot"
SERVICE_MOD_RESTART = "mod_restart"
SERVICE_RTR_RESTART = "rtr_restart"
SERVICE_SAVE_MODULE_SMC = "save_module_smc"
SERVICE_SAVE_MODULE_SMG = "save_module_smg"
SERVICE_SAVE_ROUTER_SMR = "save_router_smr"
SERVICE_SAVE_MODULE_STATUS = "save_module_status"
SERVICE_SAVE_ROUTER_STATUS = "save_router_status"
SERVICE_UPDATE_ENTITY = "update_entity"

# Hub-targeted services identify the hub via a Habitron device; the owning
# config entry (and thus the SmartHub) is resolved from the target. The device
# is optional: with a single configured hub it is inferred, so existing
# single-hub setups need not target one.
_HUB_TARGET_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICE_ID): str})
# Module addresses are 1..64; reject anything outside so a typo cannot target a
# non-existent module. "All modules" is expressed by omitting the number (not by
# a magic 255), which keeps the valid single-module range tight.
_MOD_RESTART_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): str,
        vol.Optional(MOD_NMBR): vol.All(int, vol.Range(min=1, max=64)),
    }
)
_MOD_FILE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): str,
        vol.Required(MOD_NMBR, default=1): vol.All(int, vol.Range(min=1, max=64)),
    }
)
_UPDATE_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required(HUB_UID): str,
        vol.Required(ROUTER_NMBR, default=1): int,
        vol.Required(MOD_NMBR): int,
        vol.Required(EVNT_TYPE): int,
        vol.Required(EVNT_ARG1): int,
        vol.Required(EVNT_ARG2): int,
        vol.Optional(EVNT_ARG3): int,
        vol.Optional(EVNT_ARG4): int,
        vol.Optional(EVNT_ARG5): int,
    }
)


async def _targeted_hubs(call: ServiceCall) -> list[SmartHub]:
    """Return the loaded SmartHub(s) for the call.

    A hub is selected by targeting any Habitron device (hub, router or module);
    the owning config entry is resolved via the target. When no device is
    targeted and exactly one hub is configured, that single hub is used (the
    common case); with several hubs a target is required. Raises
    ``ServiceValidationError`` when the call does not resolve to a loaded hub.
    """
    loaded = call.hass.config_entries.async_loaded_entries(DOMAIN)
    entry_ids = await async_extract_config_entry_ids(call)
    if entry_ids:
        hubs: list[SmartHub] = [
            entry.runtime_data for entry in loaded if entry.entry_id in entry_ids
        ]
    elif len(loaded) == 1:
        hubs = [loaded[0].runtime_data]
    else:
        hubs = []
    if not hubs:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hub_loaded",
        )
    return hubs


async def _async_restart_hub(call: ServiceCall) -> None:
    """Trigger a soft restart of the targeted SmartHub(s)."""
    for hub in await _targeted_hubs(call):
        await hub.comm.hub_restart()


async def _async_reboot_hub(call: ServiceCall) -> None:
    """Trigger a reboot of the targeted SmartHub(s)."""
    for hub in await _targeted_hubs(call):
        await hub.comm.hub_reboot()


async def _async_restart_module(call: ServiceCall) -> None:
    """Restart a single Habitron module, or all modules when none is given."""
    mod_nmbr = call.data.get(MOD_NMBR, RESTART_ALL)
    # RESTART_ALL is a sentinel the bus understands as-is; a real module number
    # is offset to its bus address.
    target = RESTART_ALL if mod_nmbr == RESTART_ALL else 100 + mod_nmbr
    for hub in await _targeted_hubs(call):
        await hub.comm.module_restart(target)


async def _async_restart_router(call: ServiceCall) -> None:
    """Restart the router of the targeted hub(s)."""
    for hub in await _targeted_hubs(call):
        await hub.comm.module_restart(0)


async def _async_save_module_smc(call: ServiceCall) -> None:
    """Persist a module's .smc file."""
    mod_nmbr = call.data.get(MOD_NMBR, 1)
    for hub in await _targeted_hubs(call):
        await hub.comm.save_smc_file(100 + mod_nmbr)


async def _async_save_module_smg(call: ServiceCall) -> None:
    """Persist a module's .smg file."""
    mod_nmbr = call.data.get(MOD_NMBR, 1)
    for hub in await _targeted_hubs(call):
        await hub.comm.save_smg_file(100 + mod_nmbr)


async def _async_save_router_smr(call: ServiceCall) -> None:
    """Persist the router's .smr file."""
    for hub in await _targeted_hubs(call):
        await hub.comm.save_smr_file()


async def _async_save_module_status(call: ServiceCall) -> None:
    """Persist a module's status to disk."""
    mod_nmbr = call.data.get(MOD_NMBR, 1)
    for hub in await _targeted_hubs(call):
        await hub.comm.save_module_status(100 + mod_nmbr)


async def _async_save_router_status(call: ServiceCall) -> None:
    """Persist the router status to disk."""
    for hub in await _targeted_hubs(call):
        await hub.comm.save_router_status()


async def _async_update_entity(call: ServiceCall) -> None:
    """Forward an entity-state update event to the matching hub."""
    hub_id: str = call.data[HUB_UID]
    mod_id: int = call.data[MOD_NMBR]
    evnt: int = call.data[EVNT_TYPE]
    arg1: int = call.data[EVNT_ARG1]
    arg2: int = call.data[EVNT_ARG2]
    arg3: int = call.data.get(EVNT_ARG3, 0)
    arg4: int = call.data.get(EVNT_ARG4, 0)
    arg5: int = call.data.get(EVNT_ARG5, 0)
    for entry in call.hass.config_entries.async_loaded_entries(DOMAIN):
        hub: SmartHub = entry.runtime_data
        if hub.host == hub_id:
            await hub.comm.update_entity(
                hub_id, mod_id, evnt, arg1, arg2, arg3, arg4, arg5
            )
            return
    # No loaded hub owns this address yet. This is normally a brief startup
    # race (the hub posts an event before its host is resolved); the next poll
    # reconciles state, so drop the event quietly instead of raising an error.
    _LOGGER.debug("No loaded SmartHub matches host %s; ignoring event", hub_id)


_ServiceHandler = Callable[[ServiceCall], Coroutine[Any, Any, None]]

_SERVICE_REGISTRY: tuple[tuple[str, _ServiceHandler, vol.Schema], ...] = (
    (SERVICE_HUB_RESTART, _async_restart_hub, _HUB_TARGET_SCHEMA),
    (SERVICE_HUB_REBOOT, _async_reboot_hub, _HUB_TARGET_SCHEMA),
    (SERVICE_MOD_RESTART, _async_restart_module, _MOD_RESTART_SCHEMA),
    (SERVICE_RTR_RESTART, _async_restart_router, _HUB_TARGET_SCHEMA),
    (SERVICE_SAVE_MODULE_SMC, _async_save_module_smc, _MOD_FILE_SCHEMA),
    (SERVICE_SAVE_MODULE_SMG, _async_save_module_smg, _MOD_FILE_SCHEMA),
    (SERVICE_SAVE_ROUTER_SMR, _async_save_router_smr, _HUB_TARGET_SCHEMA),
    (SERVICE_SAVE_MODULE_STATUS, _async_save_module_status, _MOD_FILE_SCHEMA),
    (SERVICE_SAVE_ROUTER_STATUS, _async_save_router_status, _HUB_TARGET_SCHEMA),
    (SERVICE_UPDATE_ENTITY, _async_update_entity, _UPDATE_ENTITY_SCHEMA),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register every Habitron domain service. Idempotent.

    Called once from the integration's ``async_setup``; the services live for
    the lifetime of the integration.
    """
    if hass.services.has_service(DOMAIN, SERVICE_HUB_RESTART):
        return
    for name, handler, schema in _SERVICE_REGISTRY:
        hass.services.async_register(DOMAIN, name, handler, schema=schema)
