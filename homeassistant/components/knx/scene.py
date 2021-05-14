"""Support for KNX scenes."""
from __future__ import annotations

from typing import Any

from xknx.devices import Scene as XknxScene

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the scenes for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxScene):
            entities.append(KNXScene(device))
    async_add_entities(entities)


class KNXScene(KnxEntity, Scene):
    """Representation of a KNX scene."""

    def __init__(self, device: XknxScene) -> None:
        """Init KNX scene."""
        self._device: XknxScene
        super().__init__(device)
        self._unique_id = (
            f"{self._device.scene_value.group_address}_{self._device.scene_number}"
        )

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.run()
