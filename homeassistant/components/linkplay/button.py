"""Support for LinkPlay buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Concatenate

from linkplay.bridge import LinkPlayBridge

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LinkPlayConfigEntry, LinkPlayRequestException
from .const import DOMAIN
from .utils import MANUFACTURER_GENERIC, get_info_from_project

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinkPlayButtonEntityDescription(ButtonEntityDescription):
    """Class describing LinkPlay button entities."""

    remote_function: Callable[[LinkPlayBridge], Coroutine[Any, Any, None]]


BUTTON_TYPES: tuple[LinkPlayButtonEntityDescription, ...] = (
    LinkPlayButtonEntityDescription(
        key="timesync",
        translation_key="timesync",
        remote_function=lambda linkplay_bridge: linkplay_bridge.device.timesync(),
        entity_category=EntityCategory.CONFIG,
    ),
    LinkPlayButtonEntityDescription(
        key="restart",
        translation_key="restart",
        remote_function=lambda linkplay_bridge: linkplay_bridge.device.reboot(),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinkPlayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LinkPlay buttons from config entry."""

    # add entities
    async_add_entities(
        [
            LinkPlayButton(config_entry.runtime_data.bridge, description)
            for description in BUTTON_TYPES
        ]
    )


def exception_wrap[_LinkPlayEntityT: LinkPlayButton, **_P, _R](
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


class LinkPlayButton(ButtonEntity):
    """Representation of LinkPlay button."""

    _attr_has_entity_name = True

    bridge: LinkPlayBridge
    entity_description: LinkPlayButtonEntityDescription

    def __init__(
        self,
        bridge: LinkPlayBridge,
        description: LinkPlayButtonEntityDescription,
    ) -> None:
        """Initialize LinkPlay button."""
        super().__init__()
        self.bridge = bridge
        self.entity_description = description
        self._attr_unique_id = f"{bridge.device.uuid}-{description.key}"

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

    @exception_wrap
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.remote_function(self.bridge)
