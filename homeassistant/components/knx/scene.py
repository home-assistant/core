"""Support for KNX scene entities."""

from __future__ import annotations

from typing import Any

from xknx.devices import Device as XknxDevice, Scene as XknxScene

from homeassistant import config_entries
from homeassistant.components.scene import BaseScene
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import KNX_ADDRESS, KNX_MODULE_KEY
from .entity import KnxYamlEntity
from .knx_module import KNXModule
from .schema import SceneSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up scene(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.SCENE]

    async_add_entities(KNXScene(knx_module, entity_config) for entity_config in config)


class KNXScene(KnxYamlEntity, BaseScene):
    """Representation of a KNX scene."""

    _device: XknxScene

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Init KNX scene."""
        super().__init__(
            knx_module=knx_module,
            device=XknxScene(
                xknx=knx_module.xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                scene_number=config[SceneSchema.CONF_SCENE_NUMBER],
            ),
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = (
            f"{self._device.scene_value.group_address}_{self._device.scene_number}"
        )

    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.run()

    def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self._async_record_activation()
        super().after_update_callback(device)
