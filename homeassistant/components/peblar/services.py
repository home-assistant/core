"""Services for the Peblar integration."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum

from peblar import (
    Peblar,
    PeblarApi,
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
)
import probatio

from homeassistant.const import CONF_ALIAS, CONF_DESCRIPTION, CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_get_config_entry,
    async_register_admin_service,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import CONF_EVCC_ID, DOMAIN
from .coordinator import PeblarConfigEntry


class PeblarService(StrEnum):
    """Store keys for Peblar services."""

    LIST_RFID_TOKENS = "list_rfid_tokens"
    ADD_RFID_TOKEN = "add_rfid_token"
    DELETE_RFID_TOKEN = "delete_rfid_token"
    LIST_VEHICLE_TOKENS = "list_vehicle_tokens"
    ADD_VEHICLE_TOKEN = "add_vehicle_token"
    DELETE_VEHICLE_TOKEN = "delete_vehicle_token"
    AUTHORIZE_CHARGE_SESSION = "authorize_charge_session"
    GET_METER_HISTORY = "get_meter_history"


class PeblarServiceArgument(StrEnum):
    """Store keys for Peblar service arguments."""

    UID = "uid"
    DESCRIPTION = "description"
    EVCC_ID = "evcc_id"
    ALIAS = "alias"
    AFTER = "after"
    BEFORE = "before"


CHARGER_SCHEMA = probatio.Schema(
    {probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str}
)

METER_HISTORY_SCHEMA = CHARGER_SCHEMA.extend(
    {
        probatio.Optional(PeblarServiceArgument.AFTER): cv.datetime,
        probatio.Optional(PeblarServiceArgument.BEFORE): cv.datetime,
    }
)

TOKEN_SCHEMA = CHARGER_SCHEMA.extend(
    {probatio.Required(PeblarServiceArgument.UID): str}
)
ADD_TOKEN_SCHEMA = TOKEN_SCHEMA.extend(
    {probatio.Required(PeblarServiceArgument.DESCRIPTION): str}
)

VEHICLE_SCHEMA = CHARGER_SCHEMA.extend(
    {probatio.Required(PeblarServiceArgument.EVCC_ID): str}
)
ADD_VEHICLE_SCHEMA = VEHICLE_SCHEMA.extend(
    {probatio.Required(PeblarServiceArgument.ALIAS): str}
)

# The charger takes the token by UID or by description, and wants exactly
# one of the two.
AUTHORIZE_SCHEMA = probatio.All(
    CHARGER_SCHEMA.extend(
        {
            probatio.Exclusive(PeblarServiceArgument.UID, "token"): str,
            probatio.Exclusive(PeblarServiceArgument.DESCRIPTION, "token"): str,
        }
    ),
    probatio.AtLeastOne(PeblarServiceArgument.UID, PeblarServiceArgument.DESCRIPTION),
)


def _get_peblar(hass: HomeAssistant, entry_id: str) -> Peblar:
    """Return the client for a charger, whatever hardware it carries."""
    entry: PeblarConfigEntry = async_get_config_entry(hass, DOMAIN, entry_id)
    return entry.runtime_data.user_configuration_coordinator.peblar


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


def _get_authorizing_api(hass: HomeAssistant, entry_id: str) -> PeblarApi:
    """Return the local REST API, for a charger that authorizes sessions.

    Presenting a token lives on the local REST API rather than the web
    one, unlike the actions that manage the lists it draws from.

    The token comes from the standalone authorization list, so the reader
    has to be there. Beyond that there are two ways for this to be
    pointless: a charger managed by a backoffice over OCPP decides for
    itself and refuses the request, and a charger set to charge without
    authorization has nothing to authorize in the first place.
    """
    entry: PeblarConfigEntry = async_get_config_entry(hass, DOMAIN, entry_id)
    runtime_data = entry.runtime_data

    if not runtime_data.system_information.hardware_has_rfid:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_rfid_hardware",
            translation_placeholders={"charger": entry.title},
        )

    configuration = runtime_data.user_configuration_coordinator.data

    if configuration.secc_ocpp_active:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="managed_by_backoffice",
            translation_placeholders={"charger": entry.title},
        )

    if configuration.session_manager_charge_without_authentication:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="authorization_not_required",
            translation_placeholders={"charger": entry.title},
        )

    return runtime_data.data_coordinator.api


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
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
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
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        peblar = _get_rfid_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.add_rfid_token(
                rfid_token_uid=call.data[PeblarServiceArgument.UID],
                rfid_token_description=call.data[PeblarServiceArgument.DESCRIPTION],
            )

    async def _handle_delete_rfid_token(call: ServiceCall) -> None:
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        peblar = _get_rfid_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.delete_rfid_token(uid=call.data[PeblarServiceArgument.UID])

    async def _handle_authorize_charge_session(call: ServiceCall) -> None:
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        api = _get_authorizing_api(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await api.authorize_charge_session(
                token=call.data.get(PeblarServiceArgument.UID),
                name=call.data.get(PeblarServiceArgument.DESCRIPTION),
            )

    async def _handle_get_meter_history(call: ServiceCall) -> ServiceResponse:
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        peblar = _get_peblar(hass, entry_id)

        # A naive moment is read by the charger as its own local time, which
        # is not necessarily the one Home Assistant runs in. Both bounds are
        # anchored here instead, the way the datetime platform does it.
        after = call.data.get(PeblarServiceArgument.AFTER)
        before = call.data.get(PeblarServiceArgument.BEFORE)
        async with _handle_peblar_errors(hass, entry_id):
            history = await peblar.meter_history(
                start=None if after is None else dt_util.as_utc(after),
                stop=None if before is None else dt_util.as_utc(before),
            )

        sessions: list[JsonValueType] = []
        for index, session in enumerate(history.session):
            end_energy_kwh = None
            end_time = None
            energy_kwh = None
            if (end_energy := session.session_end_energy_mwh) is not None:
                end_energy_kwh = end_energy / 1000000
                energy_kwh = (end_energy - session.session_start_energy_mwh) / 1000000
            if session.session_end_time is not None:
                end_time = dt_util.utc_from_timestamp(
                    session.session_end_time
                ).isoformat()
            sessions.append(
                {
                    "session_number": session.session_number,
                    "uid": session.auth_token,
                    "start_time": dt_util.utc_from_timestamp(
                        session.session_start_time
                    ).isoformat(),
                    "end_time": end_time,
                    "start_energy_kwh": session.session_start_energy_mwh / 1000000,
                    "end_energy_kwh": end_energy_kwh,
                    "energy_kwh": energy_kwh,
                    "checksum": session.checksum,
                    # The charger may return fewer outcomes than sessions.
                    "corrupted": (
                        history.corrupted_session[index]
                        if index < len(history.corrupted_session)
                        else None
                    ),
                }
            )

        return {"corrupted": history.corrupted, "sessions": sessions}

    async def _handle_list_vehicle_tokens(call: ServiceCall) -> ServiceResponse:
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
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
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        peblar = _get_autocharge_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.add_vehicle_token(
                evcc_id=call.data[PeblarServiceArgument.EVCC_ID],
                alias=call.data[PeblarServiceArgument.ALIAS],
            )

    async def _handle_delete_vehicle_token(call: ServiceCall) -> None:
        entry_id = call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        peblar = _get_autocharge_peblar(hass, entry_id)
        async with _handle_peblar_errors(hass, entry_id):
            await peblar.delete_vehicle_token(
                evcc_id=call.data[PeblarServiceArgument.EVCC_ID]
            )

    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.LIST_RFID_TOKENS,
        _handle_list_rfid_tokens,
        schema=CHARGER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.ADD_RFID_TOKEN,
        _handle_add_rfid_token,
        schema=ADD_TOKEN_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.DELETE_RFID_TOKEN,
        _handle_delete_rfid_token,
        schema=TOKEN_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.LIST_VEHICLE_TOKENS,
        _handle_list_vehicle_tokens,
        schema=CHARGER_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.ADD_VEHICLE_TOKEN,
        _handle_add_vehicle_token,
        schema=ADD_VEHICLE_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.DELETE_VEHICLE_TOKEN,
        _handle_delete_vehicle_token,
        schema=VEHICLE_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.AUTHORIZE_CHARGE_SESSION,
        _handle_authorize_charge_session,
        schema=AUTHORIZE_SCHEMA,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        PeblarService.GET_METER_HISTORY,
        _handle_get_meter_history,
        schema=METER_HISTORY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
