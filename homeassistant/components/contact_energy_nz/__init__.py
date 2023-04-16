"""The Contact Energy NZ integration."""
from __future__ import annotations

import logging

from contact_energy_nz import AuthException, ContactEnergyApi

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
TOKEN = "token"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Contact Energy NZ component."""

    hass.data[DOMAIN] = config
    return True


def _handle_auth_failure(
    hass: HomeAssistant, entry: ConfigEntry, err: Exception
) -> bool:
    _LOGGER.debug("Authentication error: %s", err)
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=entry.data,
        )
    )
    return False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Contact Energy NZ from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    keys = entry.data.keys()
    if TOKEN in keys and entry.data[TOKEN] is not None:
        connector = ContactEnergyApi.from_token(entry.data[CONF_TOKEN])
    else:
        try:
            # This method will attempt to authenticate and grab a token. If creds are wrong - it'll throw AuthException
            connector = await ContactEnergyApi.from_credentials(
                entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
            )
        except AuthException as err:
            return _handle_auth_failure(hass, entry, err)

    try:
        # this can fail with dictionary key not found errors if token is invalid - we will try reauthenticate and update token
        await connector.account_summary()
    except (KeyError, IndexError) as err:
        # if we were initialised via token - remove it and call ourselves again
        if TOKEN in keys:
            data_copy = dict(entry.data)
            del data_copy[TOKEN]
            hass.config_entries.async_update_entry(
                entry,
                data={**data_copy},
            )
            return await async_setup_entry(hass, entry)
        return _handle_auth_failure(hass, entry, err)

    # if initialisation went through - save token for later
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_TOKEN: connector.token},
    )

    hass.data[DOMAIN][entry.entry_id] = connector

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
