"""The Sifely smart lock integration.

Provides remote lock control, state monitoring and passcode management through
the Sifely Cloud API. Configured from the UI by signing in with a Sifely
account; tokens are cached in the config entry.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from pysifely import DEFAULT_BASE_URL, PASSCODE_OP_REMOTE, SifelyApiClient, SifelyApiError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_BASE_URL,
    CONF_CLIENT_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from .coordinator import SifelyConfigEntry, SifelyDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR]

SERVICE_LIST_PASSCODES = "list_passcodes"
SERVICE_ADD_PASSCODE = "add_passcode"
SERVICE_DELETE_PASSCODE = "delete_passcode"

_LIST_PASSCODES_SCHEMA = vol.Schema({vol.Required("lock_id"): vol.Coerce(int)})

_ADD_PASSCODE_SCHEMA = vol.Schema(
    {
        vol.Required("lock_id"): vol.Coerce(int),
        vol.Required("keyboard_pwd"): cv.string,
        vol.Required("keyboard_pwd_name"): cv.string,
        vol.Required("start_date"): vol.Coerce(int),
        vol.Required("end_date"): vol.Coerce(int),
        vol.Optional("keyboard_pwd_type"): vol.Coerce(int),
        vol.Optional("add_type", default=PASSCODE_OP_REMOTE): vol.Coerce(int),
    }
)

_DELETE_PASSCODE_SCHEMA = vol.Schema(
    {
        vol.Required("lock_id"): vol.Coerce(int),
        vol.Required("keyboard_pwd_id"): vol.Coerce(int),
        vol.Optional("delete_type", default=PASSCODE_OP_REMOTE): vol.Coerce(int),
    }
)


def _find_client_for_lock(hass: HomeAssistant, lock_id: int) -> SifelyApiClient:
    """Return the API client of the account that owns the given lock.

    Falls back to any available client when the owner cannot be determined.
    """
    fallback: SifelyApiClient | None = None
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coordinator: SifelyDataUpdateCoordinator = entry.runtime_data
        fallback = fallback or coordinator.client
        if any(lk.get("lockId") == lock_id for lk in coordinator.locks):
            return coordinator.client
    if fallback is None:
        raise HomeAssistantError("Could not find a usable Sifely account client")
    return fallback


def _register_services(hass: HomeAssistant) -> None:
    """Register the passcode management services (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_LIST_PASSCODES):
        return

    async def _handle_list(call: ServiceCall) -> ServiceResponse:
        lock_id = call.data["lock_id"]
        client = _find_client_for_lock(hass, lock_id)
        try:
            passcodes = await client.list_passcodes(lock_id)
        except SifelyApiError as err:
            raise HomeAssistantError(
                f"Failed to retrieve the passcode list: {err}"
            ) from err
        return {"passcodes": passcodes}

    async def _handle_add(call: ServiceCall) -> ServiceResponse:
        lock_id = call.data["lock_id"]
        client = _find_client_for_lock(hass, lock_id)
        try:
            result = await client.add_passcode(
                lock_id=lock_id,
                keyboard_pwd=call.data["keyboard_pwd"],
                keyboard_pwd_name=call.data["keyboard_pwd_name"],
                start_date=call.data["start_date"],
                end_date=call.data["end_date"],
                keyboard_pwd_type=call.data.get("keyboard_pwd_type"),
                add_type=call.data["add_type"],
            )
        except SifelyApiError as err:
            raise HomeAssistantError(f"Failed to add passcode: {err}") from err
        return dict(result)

    async def _handle_delete(call: ServiceCall) -> None:
        lock_id = call.data["lock_id"]
        client = _find_client_for_lock(hass, lock_id)
        try:
            await client.delete_passcode(
                lock_id=lock_id,
                keyboard_pwd_id=call.data["keyboard_pwd_id"],
                delete_type=call.data["delete_type"],
            )
        except SifelyApiError as err:
            raise HomeAssistantError(f"Failed to delete passcode: {err}") from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_PASSCODES,
        _handle_list,
        schema=_LIST_PASSCODES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PASSCODE,
        _handle_add,
        schema=_ADD_PASSCODE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PASSCODE,
        _handle_delete,
        schema=_DELETE_PASSCODE_SCHEMA,
    )


async def async_setup_entry(hass: HomeAssistant, entry: SifelyConfigEntry) -> bool:
    """Set up Sifely from a config entry."""
    access_token = entry.data[CONF_ACCESS_TOKEN]
    refresh_token = entry.data.get(CONF_REFRESH_TOKEN, "")
    base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
    client_id = entry.data.get(CONF_CLIENT_ID, "")

    session = async_get_clientsession(hass)

    async def _on_token_refresh(
        new_access_token: str, new_refresh_token: str
    ) -> None:
        """Persist refreshed tokens back to the config entry."""
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: new_access_token,
                CONF_REFRESH_TOKEN: new_refresh_token,
            },
        )

    client = SifelyApiClient(
        base_url=base_url,
        access_token=access_token,
        session=session,
        refresh_token=refresh_token,
        client_id=client_id,
        on_token_refresh=_on_token_refresh,
    )

    coordinator = SifelyDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SifelyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
