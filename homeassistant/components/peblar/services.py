"""Services for the Peblar integration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from peblar import Peblar, PeblarAuthenticationError, PeblarConnectionError, PeblarError
import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_ALIAS, CONF_DESCRIPTION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import (
    async_get_config_entry,
    async_register_admin_service,
)

from .const import CONF_EVCC_ID, CONF_UID, DOMAIN
from .coordinator import PeblarConfigEntry

SERVICE_ADD_RFID_TOKEN = "add_rfid_token"
SERVICE_ADD_VEHICLE_TOKEN = "add_vehicle_token"
SERVICE_DELETE_RFID_TOKEN = "delete_rfid_token"
SERVICE_DELETE_VEHICLE_TOKEN = "delete_vehicle_token"
SERVICE_LIST_RFID_TOKENS = "list_rfid_tokens"
SERVICE_LIST_VEHICLE_TOKENS = "list_vehicle_tokens"

CHARGER_SCHEMA = vol.Schema({vol.Required(ATTR_CONFIG_ENTRY_ID): str})

TOKEN_SCHEMA = CHARGER_SCHEMA.extend({vol.Required(CONF_UID): str})
ADD_TOKEN_SCHEMA = TOKEN_SCHEMA.extend({vol.Required(CONF_DESCRIPTION): str})

VEHICLE_SCHEMA = CHARGER_SCHEMA.extend({vol.Required(CONF_EVCC_ID): str})
ADD_VEHICLE_SCHEMA = VEHICLE_SCHEMA.extend({vol.Required(CONF_ALIAS): str})


def _get_rfid_peblar(hass: HomeAssistant, entry_id: str) -> Peblar:
    """Return the client, for a charger that has an RFID reader.

    The standalone authorization list lives on the reader, so a charger
    without one is turned away here instead of failing somewhere inside
    the charger.
    """
    entry: PeblarConfigEntry = async_get_config_entry(hass, DOMAIN, entry_id)

    if not entry.runtime_data.system_information.hardware_has_rfid:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_rfid_hardware",
            translation_placeholders={"charger": entry.title},
        )

    return entry.runtime_data.user_configuration_coordinator.peblar


def _get_autocharge_peblar(hass: HomeAssistant, entry_id: str) -> Peblar:
    """Return the client, for a charger that can do autocharge.

    Autocharge identifies a car by what its own controller presents over
    the power line, so it takes the PLC hardware. Without it the charger
    still hands out the list, but refuses to change it, so this turns the
    charger away rather than let that come back as a failed request.
    """
    entry: PeblarConfigEntry = async_get_config_entry(hass, DOMAIN, entry_id)

    if not entry.runtime_data.system_information.hardware_has_plc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_autocharge_hardware",
            translation_placeholders={"charger": entry.title},
        )

    return entry.runtime_data.user_configuration_coordinator.peblar


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
        peblar = _get_rfid_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            tokens = await peblar.rfid_tokens()
        return {
            "tokens": [
                {
                    "uid": token.rfid_token_uid,
                    CONF_DESCRIPTION: token.rfid_token_description,
                }
                for token in tokens
            ]
        }

    async def _handle_add_rfid_token(call: ServiceCall) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_rfid_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.add_rfid_token(
                rfid_token_uid=call.data[CONF_UID],
                rfid_token_description=call.data[CONF_DESCRIPTION],
            )

    async def _handle_delete_rfid_token(call: ServiceCall) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_rfid_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.delete_rfid_token(uid=call.data[CONF_UID])

    async def _handle_list_vehicle_tokens(call: ServiceCall) -> ServiceResponse:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_autocharge_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            vehicles = await peblar.vehicle_tokens()
        return {
            "vehicles": [
                {CONF_EVCC_ID: vehicle.evcc_id, CONF_ALIAS: vehicle.alias}
                for vehicle in vehicles
            ]
        }

    async def _handle_add_vehicle_token(call: ServiceCall) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_autocharge_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.add_vehicle_token(
                evcc_id=call.data[CONF_EVCC_ID],
                alias=call.data[CONF_ALIAS],
            )

    async def _handle_delete_vehicle_token(call: ServiceCall) -> None:
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        peblar = _get_autocharge_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.delete_vehicle_token(evcc_id=call.data[CONF_EVCC_ID])

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LIST_RFID_TOKENS,
        _handle_list_rfid_tokens,
        schema=CHARGER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ADD_RFID_TOKEN,
        _handle_add_rfid_token,
        schema=ADD_TOKEN_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_RFID_TOKEN,
        _handle_delete_rfid_token,
        schema=TOKEN_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LIST_VEHICLE_TOKENS,
        _handle_list_vehicle_tokens,
        schema=CHARGER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ADD_VEHICLE_TOKEN,
        _handle_add_vehicle_token,
        schema=ADD_VEHICLE_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_VEHICLE_TOKEN,
        _handle_delete_vehicle_token,
        schema=VEHICLE_SCHEMA,
    )
