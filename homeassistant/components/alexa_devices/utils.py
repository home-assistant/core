"""Utils for Alexa Devices."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aioamazondevices.const import SPEAKER_GROUP_FAMILY
from aioamazondevices.exceptions import CannotConnect, CannotRetrieveData

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from .const import _LOGGER, DOMAIN
from .coordinator import AmazonDevicesCoordinator
from .entity import AmazonEntity


def alexa_api_call[_T: AmazonEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Catch Alexa API call exceptions."""

    @wraps(func)
    async def cmd_wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Wrap all command methods."""
        try:
            await func(self, *args, **kwargs)
        except CannotConnect as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotRetrieveData as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_retrieve_data_with_error",
                translation_placeholders={"error": repr(err)},
            ) from err

    return cmd_wrapper


async def async_update_unique_id(
    hass: HomeAssistant,
    coordinator: AmazonDevicesCoordinator,
    domain: str,
    old_key: str,
    new_key: str,
    remove_from_group: bool = False,
) -> None:
    """Update unique id for entities created with old format."""
    entity_registry = er.async_get(hass)

    for serial_num in coordinator.data:
        unique_id = f"{serial_num}-{old_key}"
        if entity_id := entity_registry.async_get_entity_id(domain, DOMAIN, unique_id):
            _LOGGER.debug("Updating unique_id for %s", entity_id)
            new_unique_id = unique_id.replace(old_key, new_key)

            # Remove from the group
            if (
                remove_from_group
                and coordinator.data[serial_num].device_family == SPEAKER_GROUP_FAMILY
            ):
                entity_registry.async_remove(entity_id)
                continue

            # Update the registry with the new unique_id
            entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)
