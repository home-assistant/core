"""Services for the Plex integration."""
import logging

from imow.api import IMowApi
from imow.common.actions import IMowActions
from imow.common.mowerstate import MowerState
import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

IMOW_INTENT_SCHEMA = vol.Schema(
    {
        vol.Optional("mower_id"): int,
        vol.Optional("mower_external_id"): str,
        vol.Optional("mower_name"): str,
        vol.Optional("duration"): int,
        vol.Optional("startpoint"): int,
        vol.Optional("device_id"): any,
        vol.Optional("entity_id"): any,
        vol.Required("action"): str,
    }
)

_LOGGER = logging.getLogger(__package__)


async def async_setup_services(hass, entry):
    """Set up services for the iMow component."""

    async def async_call_intent_service(service_call):
        await intent_service(hass, entry, service_call)

    hass.services.async_register(
        DOMAIN,
        "intent",
        async_call_intent_service,
        schema=IMOW_INTENT_SCHEMA,
    )

    return True


async def intent_service(hass, entry, service_call):
    """Call correct iMow service."""
    service_data_mower_id = (
        service_call.data["mower_id"] if "mower_id" in service_call.data else None
    )
    service_data_mower_name = (
        service_call.data["mower_name"] if "mower_name" in service_call.data else None
    )
    service_data_mower_action_duration = (
        service_call.data["duration"] if "duration" in service_call.data else None
    )
    service_data_mower_action_startpoint = (
        service_call.data["startpoint"] if "startpoint" in service_call.data else None
    )
    api: IMowApi = hass.data[DOMAIN][entry.entry_id]["api"]

    if not service_data_mower_id and not service_data_mower_name:
        raise HomeAssistantError("Failure: Need one of 'mower_id' or 'mower_name'")

    try:
        mower_state: MowerState
        service_data_mower_action = IMowActions(service_call.data["action"])
        if service_data_mower_name:
            mower_state: MowerState = await api.receive_mower_by_name(
                service_data_mower_name
            )
        if service_data_mower_id:
            mower_state: MowerState = await api.receive_mower_by_id(
                service_data_mower_id
            )

        if (
            service_data_mower_action_startpoint
            and not service_data_mower_action_duration
        ):
            await mower_state.intent(
                imow_action=service_data_mower_action,
                startpoint=service_data_mower_action_startpoint,
            )
        if (
            not service_data_mower_action_startpoint
            and service_data_mower_action_duration
        ):
            await mower_state.intent(
                imow_action=service_data_mower_action,
                duration=service_data_mower_action_duration,
            )

        if (
            not service_data_mower_action_startpoint
            and not service_data_mower_action_duration
        ):
            await mower_state.intent(imow_action=service_data_mower_action)

        if service_data_mower_action_startpoint and service_data_mower_action_duration:
            await mower_state.intent(
                imow_action=service_data_mower_action,
                startpoint=service_data_mower_action_startpoint,
                duration=service_data_mower_action_duration,
            )

        _LOGGER.debug(f"Doing {service_data_mower_action} with {mower_state.name}")
    except LookupError as e:
        _LOGGER.exception(e)
        raise HomeAssistantError(e)
    except ValueError as e:
        _LOGGER.exception(e)
        raise HomeAssistantError(e)

    return True
