"""ISEO Argo BLE Lock — Home Assistant integration."""

from __future__ import annotations

import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.ec import SECP224R1, derive_private_key
from iseo_argo_ble import IseoClient

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ADDRESS,
    CONF_PRIV_SCALAR,
    CONF_UUID,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
    PLATFORMS,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

type IseoConfigEntry = ConfigEntry[IseoClient]


async def async_setup_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Set up ISEO Argo BLE Lock from a config entry."""
    address = entry.data[CONF_ADDRESS]
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            f"Could not find ISEO lock {address} — is it powered on and in range?"
        )

    priv_int = int(entry.data[CONF_PRIV_SCALAR], 16)
    priv = await hass.async_add_executor_job(
        derive_private_key, priv_int, SECP224R1(), default_backend()
    )
    uuid_bytes = bytes.fromhex(entry.data[CONF_UUID])

    client = IseoClient(
        address=address,
        uuid_bytes=uuid_bytes,
        identity_priv=priv,
        subtype=DEFAULT_USER_SUBTYPE,
        ble_device=ble_device,
    )

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
