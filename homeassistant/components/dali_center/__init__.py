"""The Dali Center integration."""

from __future__ import annotations

import logging
from typing import Any

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [Platform.LIGHT]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Set up Dali Center from a config entry."""

    gateway: DaliGateway = DaliGateway(entry.data["gateway"])
    gw_sn = gateway.gw_sn

    try:
        await gateway.connect()
        _LOGGER.info("Successfully connected to gateway %s", gw_sn)
    except DaliGatewayError as exc:
        _LOGGER.exception("Error connecting to gateway %s", gw_sn)
        raise ConfigEntryNotReady(
            "You can try to delete the gateway and add it again"
        ) from exc

    def on_online_status(dev_id: str, available: bool) -> None:
        signal = f"dali_center_update_available_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, available)

    def on_device_status(dev_id: str, property_list: list[dict[str, Any]]) -> None:
        signal = f"dali_center_update_{dev_id}"
        hass.add_job(async_dispatcher_send, hass, signal, property_list)

    gateway.on_online_status = on_online_status
    gateway.on_device_status = on_device_status

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gw_sn)},
        manufacturer=MANUFACTURER,
        name=gateway.name,
        model="SR-GW-EDA",
        serial_number=gw_sn,
    )

    entry.runtime_data = DaliCenterData(gateway=gateway)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    _LOGGER.info("DALI Center gateway %s setup completed successfully", gw_sn)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
