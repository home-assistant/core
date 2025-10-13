"""The DALI Center integration."""

from __future__ import annotations

import logging

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_GATEWAY_DATA, DOMAIN, MANUFACTURER
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [Platform.LIGHT]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Set up DALI Center from a config entry."""

    gateway = DaliGateway(entry.data[CONF_GATEWAY_DATA])
    gw_sn = gateway.gw_sn

    try:
        await gateway.connect()
    except DaliGatewayError as exc:
        raise ConfigEntryNotReady(
            "You can try to delete the gateway and add it again"
        ) from exc

    _LOGGER.info("Successfully connected to gateway %s", gw_sn)

    try:
        device_data_list = await gateway.discover_devices()
    except DaliGatewayError as exc:
        raise ConfigEntryNotReady(
            "Unable to discover devices from the gateway"
        ) from exc

    _LOGGER.debug("Discovered %d devices on gateway %s", len(device_data_list), gw_sn)

    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gw_sn)},
        manufacturer=MANUFACTURER,
        name=gateway.name,
        model="SR-GW-EDA",
        serial_number=gw_sn,
    )

    entry.runtime_data = DaliCenterData(
        gateway=gateway,
        device_data_list=device_data_list,
    )
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
