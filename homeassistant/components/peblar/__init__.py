"""Integration for Peblar EV chargers."""

from __future__ import annotations

import asyncio
from typing import cast

import voluptuous as vol
from aiohttp import CookieJar
from peblar import (
    AccessMode,
    Peblar,
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import (
    PeblarConfigEntry,
    PeblarDataUpdateCoordinator,
    PeblarRuntimeData,
    PeblarUserConfigurationDataUpdateCoordinator,
    PeblarVersionDataUpdateCoordinator,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Set up Peblar from a config entry."""

    # Set up connection to the Peblar charger
    peblar = Peblar(
        host=entry.data[CONF_HOST],
        session=async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True)),
    )
    try:
        await peblar.login(password=entry.data[CONF_PASSWORD])
        system_information = await peblar.system_information()
        api = await peblar.rest_api(enable=True, access_mode=AccessMode.READ_WRITE)
    except PeblarConnectionError as err:
        raise ConfigEntryNotReady("Could not connect to Peblar charger") from err
    except PeblarAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except PeblarError as err:
        raise ConfigEntryNotReady(
            "Unknown error occurred while connecting to Peblar charger"
        ) from err

    # Setup the data coordinators
    meter_coordinator = PeblarDataUpdateCoordinator(hass, entry, api)
    user_configuration_coordinator = PeblarUserConfigurationDataUpdateCoordinator(
        hass, entry, peblar
    )
    version_coordinator = PeblarVersionDataUpdateCoordinator(hass, entry, peblar)
    await asyncio.gather(
        meter_coordinator.async_config_entry_first_refresh(),
        user_configuration_coordinator.async_config_entry_first_refresh(),
        version_coordinator.async_config_entry_first_refresh(),
    )

    # Store the runtime data
    entry.runtime_data = PeblarRuntimeData(
        data_coordinator=meter_coordinator,
        system_information=system_information,
        user_configuration_coordinator=user_configuration_coordinator,
        version_coordinator=version_coordinator,
    )

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register RFID services once (shared across all entries)
    if not hass.services.has_service(DOMAIN, "list_rfid_tokens"):
        _async_register_services(hass)

    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register RFID management services."""

    def _get_peblar(call: ServiceCall) -> Peblar:
        entry_id: str = call.data["config_entry_id"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_config_entry",
                translation_placeholders={"config_entry_id": entry_id},
            )
        return cast(PeblarConfigEntry, entry).runtime_data.user_configuration_coordinator.peblar

    async def _handle_list_rfid_tokens(call: ServiceCall) -> ServiceResponse:
        peblar = _get_peblar(call)
        tokens = await peblar.rfid_tokens()
        return {
            "tokens": [
                {
                    "uid": t.rfid_token_uid,
                    "description": t.rfid_token_description,
                }
                for t in tokens
            ]
        }

    async def _handle_add_rfid_token(call: ServiceCall) -> None:
        peblar = _get_peblar(call)
        await peblar.add_rfid_token(
            rfid_token_uid=call.data["uid"],
            rfid_token_description=call.data["description"],
        )

    async def _handle_remove_rfid_token(call: ServiceCall) -> None:
        peblar = _get_peblar(call)
        await peblar.delete_rfid_token(uid=call.data["uid"])

    hass.services.async_register(
        DOMAIN,
        "list_rfid_tokens",
        _handle_list_rfid_tokens,
        schema=vol.Schema({vol.Required("config_entry_id"): str}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "add_rfid_token",
        _handle_add_rfid_token,
        schema=vol.Schema({
            vol.Required("config_entry_id"): str,
            vol.Required("uid"): str,
            vol.Required("description"): str,
        }),
    )
    hass.services.async_register(
        DOMAIN,
        "remove_rfid_token",
        _handle_remove_rfid_token,
        schema=vol.Schema({
            vol.Required("config_entry_id"): str,
            vol.Required("uid"): str,
        }),
    )


async def async_unload_entry(hass: HomeAssistant, entry: PeblarConfigEntry) -> bool:
    """Unload Peblar config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not hass.config_entries.async_loaded_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, "list_rfid_tokens")
        hass.services.async_remove(DOMAIN, "add_rfid_token")
        hass.services.async_remove(DOMAIN, "remove_rfid_token")
    return unloaded
