"""Services for the Peblar integration."""

from __future__ import annotations

from typing import cast

from peblar import Peblar
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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.util.json import JsonValueType

from .const import DOMAIN
from .coordinator import PeblarConfigEntry

CONF_UID = "uid"

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register RFID management services."""

    async def _handle_list_rfid_tokens(call: ServiceCall) -> ServiceResponse:
        peblar = _get_peblar(hass, call.data[ATTR_CONFIG_ENTRY_ID])
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
        peblar = _get_peblar(hass, call.data[ATTR_CONFIG_ENTRY_ID])
        await peblar.add_rfid_token(
            rfid_token_uid=call.data[CONF_UID],
            rfid_token_description=call.data[CONF_DESCRIPTION],
        )

    async def _handle_delete_rfid_token(call: ServiceCall) -> None:
        peblar = _get_peblar(hass, call.data[ATTR_CONFIG_ENTRY_ID])
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
