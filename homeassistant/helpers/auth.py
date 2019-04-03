"""Define auth and permissions helpers."""
from functools import wraps

from typing import TYPE_CHECKING, Any, Callable  # noqa: F401

from homeassistant.exceptions import Unauthorized, UnknownUser

from homeassistant.auth.permissions.const import POLICY_CONTROL

from .typing import HomeAssistantType
if TYPE_CHECKING:
    from homeassistant.core import Service, ServiceCall  # noqa


def authorized_service_call(hass: HomeAssistantType, domain: str) -> Callable:
    """Ensure user of a config entry-enabled service call has permission."""
    def decorator(service: 'Service') -> Callable:
        """Decorate."""
        @wraps(service)
        async def check_permissions(
                call: 'ServiceCall') -> Any:
            """Check user permission and raise before call if unauthorized."""
            if not call.context.user_id:
                return await service(call)

            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(
                    context=call.context, permission=POLICY_CONTROL)

            # If the user passes one or more entity IDs, check permissions
            # there; otherwise, check permissions against entities registered
            # to the domain:
            if call.data.get('entity_id'):
                if isinstance(call.data['entity'], str):
                    entities = [call.data['entity_id']]
                else:
                    entities = call.data['entity_id']
            else:
                reg = await hass.helpers.entity_registry.async_get_registry()
                entities = [
                    entity.entity_id for entity in reg.entities.values()
                    if entity.platform == domain
                ]

            for entity_id in entities:
                if user.permissions.check_entity(entity_id, POLICY_CONTROL):
                    return await service(call)

            raise Unauthorized(
                context=call.context,
                permission=POLICY_CONTROL,
            )

        return check_permissions

    return decorator
