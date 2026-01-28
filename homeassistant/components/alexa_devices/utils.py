"""Utils for Alexa Devices."""

from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate

from aioamazondevices.const.devices import SPEAKER_GROUP_FAMILY
from aioamazondevices.exceptions import CannotConnect, CannotRetrieveData

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
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
) -> None:
    """Update unique id for entities created with old format."""
    entity_registry = er.async_get(hass)

    for serial_num in coordinator.data:
        unique_id = f"{serial_num}-{old_key}"
        if entity_id := entity_registry.async_get_entity_id(domain, DOMAIN, unique_id):
            _LOGGER.debug("Updating unique_id for %s", entity_id)
            new_unique_id = unique_id.replace(old_key, new_key)

            # Update the registry with the new unique_id
            entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_remove_dnd_from_virtual_group(
    hass: HomeAssistant,
    coordinator: AmazonDevicesCoordinator,
) -> None:
    """Remove entity DND from virtual group."""
    entity_registry = er.async_get(hass)

    for serial_num in coordinator.data:
        unique_id = f"{serial_num}-do_not_disturb"
        entity_id = entity_registry.async_get_entity_id(
            DOMAIN, SWITCH_DOMAIN, unique_id
        )
        is_group = coordinator.data[serial_num].device_family == SPEAKER_GROUP_FAMILY
        if entity_id and is_group:
            entity_registry.async_remove(entity_id)
            _LOGGER.debug("Removed DND switch from virtual group %s", entity_id)
