"""Services for the HomeKit integration."""

import asyncio
import logging
from typing import cast

import probatio

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.util.async_ import create_eager_task

from .const import (
    DOMAIN,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_UNPAIR,
    STATUS_RUNNING,
)
from .util import async_all_homekit_instances, async_update_entries_from_yaml

_LOGGER = logging.getLogger(__name__)

RESET_ACCESSORY_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_ENTITY_ID): cv.entity_ids}
)


UNPAIR_SERVICE_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_DEVICE_ID): probatio.All(probatio.EnsureList(), [str])}
)


async def _async_handle_homekit_reset_accessory(service: ServiceCall) -> None:
    """Handle reset accessory HomeKit service call."""
    hass = service.hass
    for homekit in async_all_homekit_instances(hass):
        if homekit.status != STATUS_RUNNING:
            _LOGGER.warning(
                "HomeKit is not running. Either it is waiting to be "
                "started or has been stopped"
            )
            continue

        entity_ids = cast(list[str], service.data.get("entity_id"))
        await homekit.async_reset_accessories(entity_ids)


async def _async_handle_homekit_unpair(service: ServiceCall) -> None:
    """Handle unpair HomeKit service call."""
    hass = service.hass
    referenced = async_extract_referenced_entity_ids(
        hass, TargetSelection(service.data)
    )
    dev_reg = dr.async_get(hass)
    for device_id in referenced.referenced_devices:
        if not (dev_reg_ent := dev_reg.async_get(device_id)):
            raise HomeAssistantError(f"No device found for device id: {device_id}")
        if isinstance(dev_reg_ent, dr.ChildDeviceEntry):
            # A child device carries no HomeKit pairing; only its parent can.
            continue
        macs = [
            cval
            for ctype, cval in dev_reg_ent.connections
            if ctype == dr.CONNECTION_NETWORK_MAC
        ]
        matching_instances = [
            homekit
            for homekit in async_all_homekit_instances(hass)
            if homekit.driver and dr.format_mac(homekit.driver.state.mac) in macs
        ]
        if not matching_instances:
            raise HomeAssistantError(
                f"No homekit accessory found for device id: {device_id}"
            )
        for homekit in matching_instances:
            homekit.async_unpair()


async def _handle_homekit_reload(service: ServiceCall) -> None:
    """Handle start HomeKit service call."""
    hass = service.hass
    config = await async_integration_yaml_config(hass, DOMAIN)
    if not config or DOMAIN not in config:
        return
    async_update_entries_from_yaml(hass, config, start_import_flow=False)
    await asyncio.gather(
        *(
            create_eager_task(hass.config_entries.async_reload(entry.entry_id))
            for entry in hass.config_entries.async_entries(DOMAIN)
        )
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the HomeKit integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_HOMEKIT_RESET_ACCESSORY,
        _async_handle_homekit_reset_accessory,
        schema=RESET_ACCESSORY_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_HOMEKIT_UNPAIR,
        _async_handle_homekit_unpair,
        schema=UNPAIR_SERVICE_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        _handle_homekit_reload,
    )
