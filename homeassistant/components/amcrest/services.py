"""Support for Amcrest IP cameras."""

from __future__ import annotations

from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, ENTITY_MATCH_NONE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_extract_entity_ids

from .camera import CAMERA_SERVICES
from .const import CAMERAS, DATA_AMCREST, DOMAIN
from .helpers import service_signal


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Amcrest IP Camera services."""

    def have_permission(user: User | None, entity_id: str) -> bool:
        return not user or user.permissions.check_entity(entity_id, POLICY_CONTROL)

    async def async_extract_from_service(call: ServiceCall) -> list[str]:
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
        else:
            user = None

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
            # Return all entity_ids user has permission to control.
            return [
                entity_id
                for entity_id in hass.data[DATA_AMCREST][CAMERAS]
                if have_permission(user, entity_id)
            ]

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_NONE:
            return []

        call_ids = await async_extract_entity_ids(call)
        entity_ids = []
        for entity_id in hass.data[DATA_AMCREST][CAMERAS]:
            if entity_id not in call_ids:
                continue
            if not have_permission(user, entity_id):
                raise Unauthorized(
                    context=call.context, entity_id=entity_id, permission=POLICY_CONTROL
                )
            entity_ids.append(entity_id)
        return entity_ids

    async def async_service_handler(call: ServiceCall) -> None:
        args = [call.data[arg] for arg in CAMERA_SERVICES[call.service][2]]
        for entity_id in await async_extract_from_service(call):
            async_dispatcher_send(hass, service_signal(call.service, entity_id), *args)

    for service, params in CAMERA_SERVICES.items():
        hass.services.async_register(DOMAIN, service, async_service_handler, params[0])
