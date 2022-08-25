"""The MPRIS media playback remote control integration."""
from __future__ import annotations

import datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509 import Certificate
import hassmpris_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_HOST,
    CONF_MPRIS_PORT,
    CONF_TRUST_CHAIN,
    DOMAIN,
    ENTRY_CLIENT,
    ENTRY_UNLOADERS,
    LOGGER as _LOGGER,
)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=5)
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


def _load_cert_chain(chain: bytes) -> list[Certificate]:
    start_line = b"-----BEGIN CERTIFICATE-----"
    cert_slots = chain.split(start_line)
    certificates: list[Certificate] = []
    for single_pem_cert in cert_slots[1:]:
        loaded = x509.load_pem_x509_certificate(start_line + single_pem_cert)
        certificates.append(loaded)
    return certificates


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MPRIS media playback remote control from a config entry."""
    client_cert = x509.load_pem_x509_certificate(
        entry.data[CONF_CLIENT_CERT].encode("ascii"),
    )
    client_key = serialization.load_pem_private_key(
        entry.data[CONF_CLIENT_KEY].encode("ascii"),
        None,
    )
    trust_chain = _load_cert_chain(
        entry.data[CONF_TRUST_CHAIN].encode("ascii"),
    )

    clnt = hassmpris_client.AsyncMPRISClient(
        entry.data[CONF_HOST],
        entry.data[CONF_MPRIS_PORT],
        client_cert,
        client_key,
        trust_chain,
    )
    try:
        _LOGGER.debug("Pinging the server")
        await clnt.ping()
        _LOGGER.debug("Successfully pinged the server")

    except hassmpris_client.Unauthenticated as exc:
        raise ConfigEntryAuthFailed(exc) from exc
    except Exception as exc:
        _LOGGER.exception("Cannot ping the server")
        raise ConfigEntryNotReady(str(exc)) from exc

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_CLIENT: clnt,
        ENTRY_UNLOADERS: [],
    }

    hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("Closing client connection")
        await data[ENTRY_CLIENT].close()
        _LOGGER.debug("Connection closed -- running unloaders")
        unloaders = data[ENTRY_UNLOADERS]
        for unloader in reversed(unloaders):
            await unloader()
        _LOGGER.debug("Unloaders complete")

    return unload_ok
