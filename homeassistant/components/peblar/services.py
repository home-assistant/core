"""Services for the Peblar integration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from peblar import Peblar, PeblarAuthenticationError, PeblarConnectionError, PeblarError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_DESCRIPTION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util.json import JsonValueType

from .const import CONF_UID, DOMAIN
from .coordinator import PeblarConfigEntry

LIST_RESPONSE_SCHEMA = vol.Schema(
    {
        "tokens": [
            vol.Schema(
                {
                    "uid": str,
                    "description": str,
                }
            )
        ]
    }
)


def _get_peblar(hass: HomeAssistant, entry_id: str) -> Peblar:
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_config_entry",
            translation_placeholders={ATTR_CONFIG_ENTRY_ID: entry_id},
        )
    return cast(
        PeblarConfigEntry, entry
    ).runtime_data.user_configuration_coordinator.peblar


@asynccontextmanager
async def _handle_peblar_errors(
    hass: HomeAssistant, entry_id: str
) -> AsyncIterator[None]:
    """Translate Peblar library errors into Home Assistant errors."""
    try:
        yield

    except PeblarAuthenticationError as error:
        # Reload the config entry to trigger reauth flow
        hass.config_entries.async_schedule_reload(entry_id)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from error

    except PeblarConnectionError as error:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(error)},
        ) from error

    except PeblarError as error:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unknown_error",
            translation_placeholders={"error": str(error)},
        ) from error


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register RFID management services."""

    async def _handle_list_rfid_tokens(call: ServiceCall) -> ServiceResponse:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            tokens = await peblar.rfid_tokens()
        return cast(
            dict[str, JsonValueType],
            LIST_RESPONSE_SCHEMA(
                {
                    "tokens": [
                        {
                            "uid": t.rfid_token_uid,
                            CONF_DESCRIPTION: t.rfid_token_description,
                        }
                        for t in tokens
                    ]
                }
            ),
        )

    async def _handle_add_rfid_token(call: ServiceCall) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.add_rfid_token(
                rfid_token_uid=call.data[CONF_UID],
                rfid_token_description=call.data[CONF_DESCRIPTION],
            )

    async def _handle_delete_rfid_token(call: ServiceCall) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.delete_rfid_token(uid=call.data[CONF_UID])

    async_register_admin_service(
        hass,
        DOMAIN,
        "list_rfid_tokens",
        _handle_list_rfid_tokens,
        schema=vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str}),
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        "add_rfid_token",
        _handle_add_rfid_token,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required(CONF_UID): str,
                vol.Required(CONF_DESCRIPTION): str,
            }
        ),
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        "delete_rfid_token",
        _handle_delete_rfid_token,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required(CONF_UID): str,
            }
        ),
    )
