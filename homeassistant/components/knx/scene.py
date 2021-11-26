"""Support for KNX scenes."""
from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Scene as XknxScene

from homeassistant import config_entries
from homeassistant.components.scene import Scene
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DATA_KNX_CONFIG, DOMAIN, KNX_ADDRESS, SupportedPlatforms
from .knx_entity import KnxEntity
from .schema import SceneSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene(s) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][
        SupportedPlatforms.SCENE.value
    ]

    async_add_entities(KNXScene(xknx, entity_config) for entity_config in config)


class KNXScene(KnxEntity, Scene):
    """Representation of a KNX scene."""

    _device: XknxScene

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Init KNX scene."""
        super().__init__(
            device=XknxScene(
                xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                scene_number=config[SceneSchema.CONF_SCENE_NUMBER],
            )
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = (
            f"{self._device.scene_value.group_address}_{self._device.scene_number}"
        )

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.run()
