"""Support for KNX scene entities."""

from __future__ import annotations

from typing import Any

from xknx.devices import Device as XknxDevice, Scene as XknxScene

from homeassistant import config_entries
from homeassistant.components.scene import BaseScene
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, KNX_ADDRESS, KNX_MODULE_KEY, SceneConf
from .entity import (
    KnxUiEntity,
    KnxUiEntityPlatformController,
    KnxYamlEntity,
    _KnxEntityBase,
)
from .knx_module import KNXModule
from .schema import SceneSchema
from .storage.const import CONF_ENTITY, CONF_GA_SCENE
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up scene(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.SCENE,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiScene,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.SCENE):
        entities.extend(
            KnxYamlScene(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.SCENE):
        entities.extend(
            KnxUiScene(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxScene(BaseScene, _KnxEntityBase):
    """Representation of a KNX scene."""

    _device: XknxScene

    async def _async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.run()

    def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self._async_record_activation()
        super().after_update_callback(device)


class KnxYamlScene(_KnxScene, KnxYamlEntity):
    """Representation of a KNX scene configured from YAML."""

    _device: XknxScene

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize KNX scene."""
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


class KnxUiScene(_KnxScene, KnxUiEntity):
    """Representation of a KNX scene configured from the UI."""

    _device: XknxScene

    def __init__(
        self,
        knx_module: KNXModule,
        unique_id: str,
        config: ConfigType,
    ) -> None:
        """Initialize KNX scene."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxScene(
            xknx=knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            group_address=knx_conf.get_write(CONF_GA_SCENE),
            scene_number=knx_conf.get(SceneConf.SCENE_NUMBER),
        )
