"""The Sunricher DALI integration."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging

from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import CONF_SERIAL_NUMBER, DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SCENE]
_LOGGER = logging.getLogger(__name__)


def _remove_missing_devices(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    devices: Sequence[Device],
    gateway_identifier: tuple[str, str],
) -> None:
    """Detach devices that are no longer provided by the gateway."""
    device_registry = dr.async_get(hass)
    known_device_ids = {device.dev_id for device in devices}

    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if gateway_identifier in device_entry.identifiers:
            continue

        domain_device_ids = {
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        }

        if not domain_device_ids:
            continue

        if domain_device_ids.isdisjoint(known_device_ids):
            device_registry.async_update_device(
                device_entry.id,
                remove_config_entry_id=entry.entry_id,
            )


async def async_setup_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Set up Sunricher DALI from a config entry."""

    gateway = DaliGateway(
        entry.data[CONF_SERIAL_NUMBER],
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        name=entry.data[CONF_NAME],
    )
    gw_sn = gateway.gw_sn

    try:
        await gateway.connect()
    except DaliGatewayError as exc:
        raise ConfigEntryNotReady(
            "You can try to delete the gateway and add it again"
        ) from exc

    try:
        devices, scenes = await asyncio.gather(
            gateway.discover_devices(),
            gateway.discover_scenes(),
        )
    except DaliGatewayError as exc:
        raise ConfigEntryNotReady(
            "Unable to discover devices from the gateway"
        ) from exc

    _LOGGER.debug("Discovered %d devices on gateway %s", len(devices), gw_sn)

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, gw_sn)},
        identifiers={(DOMAIN, gw_sn)},
        manufacturer=MANUFACTURER,
        name=gateway.name,
        model="SR-GW-EDA",
        serial_number=gw_sn,
    )
    _remove_missing_devices(hass, entry, devices, (DOMAIN, gw_sn))

    entry.runtime_data = DaliCenterData(
        gateway=gateway,
        devices=devices,
        scenes=scenes,
    )
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.gateway.disconnect()
    return unload_ok
