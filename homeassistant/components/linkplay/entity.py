"""BaseEntity to support multiple LinkPlay platforms."""

from collections.abc import Callable, Coroutine
from typing import Any, Concatenate

from linkplay.bridge import LinkPlayBridge

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from . import DOMAIN, LinkPlayRequestException
from .utils import MANUFACTURER_GENERIC, get_info_from_project


def exception_wrap[_LinkPlayEntityT: LinkPlayBaseEntity, **_P, _R](
    func: Callable[Concatenate[_LinkPlayEntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_LinkPlayEntityT, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    async def _wrap(self: _LinkPlayEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await func(self, *args, **kwargs)
        except LinkPlayRequestException as err:
            raise HomeAssistantError(
                f"Exception occurred when communicating with API {func}: {err}"
            ) from err

    return _wrap


class LinkPlayBaseEntity(Entity):
    """Representation of a LinkPlay base entity."""

    _attr_has_entity_name = True

    def __init__(self, bridge: LinkPlayBridge) -> None:
        """Initialize the LinkPlay media player."""

        self._bridge = bridge

        manufacturer, model = get_info_from_project(bridge.device.properties["project"])
        model_id = None
        if model != MANUFACTURER_GENERIC:
            model_id = bridge.device.properties["project"]

        self._attr_device_info = dr.DeviceInfo(
            configuration_url=bridge.endpoint,
            connections={(dr.CONNECTION_NETWORK_MAC, bridge.device.properties["MAC"])},
            hw_version=bridge.device.properties["hardware"],
            identifiers={(DOMAIN, bridge.device.uuid)},
            manufacturer=manufacturer,
            model=model,
            model_id=model_id,
            name=bridge.device.name,
            sw_version=bridge.device.properties["firmware"],
        )
