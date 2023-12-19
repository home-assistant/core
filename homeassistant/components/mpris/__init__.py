"""The MPRIS media playback remote control integration."""
from __future__ import annotations

from typing import cast

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
import hassmpris_client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .cert_data import CertStore
from .const import CONF_HOST, CONF_MPRIS_PORT, DOMAIN, LOGGER as _LOGGER
from .models import ConfigEntryData, MPRISData

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MPRIS media playback remote control from a config entry."""

    # This would be an error, and the type checker knows it.
    assert entry.unique_id is not None

    try:
        client_cert, client_key, trust_chain = await CertStore(
            hass, entry.unique_id
        ).load_cert_data()
    except KeyError as exc:
        raise ConfigEntryAuthFailed(
            "Authentication data is missing -- must reauth"
        ) from exc

    entry_data = cast(ConfigEntryData, entry.data)
    clnt = hassmpris_client.AsyncMPRISClient(
        entry_data[CONF_HOST],
        entry_data[CONF_MPRIS_PORT],
        client_cert,
        cast(RSAPrivateKey, client_key),
        trust_chain,
    )
    try:
        _LOGGER.debug("Pinging the MPRIS agent")
        await clnt.ping()
        _LOGGER.info("Successfully pinged the MPRIS agent")
    except hassmpris_client.Unauthenticated as exc:
        raise ConfigEntryAuthFailed(exc) from exc
    except Exception as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    hass.data.setdefault(DOMAIN, {})
    mpris_data = hass.data[DOMAIN][entry.entry_id] = MPRISData(clnt, [])

    async def on_unload(_: Event) -> None:
        await _run_unloaders(mpris_data)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_unload)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _run_unloaders(mpris_data: MPRISData) -> None:
    _LOGGER.debug("Running unloaders")
    for unloader in reversed(mpris_data.unloaders):
        await unloader()
    _LOGGER.debug("Unloaders ran")
    _LOGGER.debug("Closing connection to agent")
    await mpris_data.client.close()
    _LOGGER.debug("Connection closed")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        mpris_data = cast(MPRISData, hass.data[DOMAIN].pop(entry.entry_id))
        await _run_unloaders(mpris_data)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    # This would be an error, and the type checker knows it.
    assert entry.unique_id
    await CertStore(hass, entry.unique_id).remove_cert_data()
