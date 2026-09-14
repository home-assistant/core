"""Support for KNX notify entities."""

from typing import override

from xknx.devices import Notification as XknxNotification

from homeassistant import config_entries
from homeassistant.components.notify import NotifyEntity
from homeassistant.const import CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, KNX_ADDRESS, KNX_MODULE_KEY
from .entity import (
    KnxUiEntity,
    KnxUiEntityPlatformController,
    KnxYamlEntity,
    build_yaml_unique_id,
)
from .knx_module import KNXModule
from .storage.const import CONF_ENTITY, CONF_GA_SEND
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up notify(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.NOTIFY,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiNotify,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.NOTIFY):
        entities.extend(
            KnxYamlNotify(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.get_entity_configs(Platform.NOTIFY):
        entities.extend(
            KnxUiNotify(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxNotify(NotifyEntity):
    """Representation of a KNX notification entity."""

    _device: XknxNotification

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification to knx bus."""
        await self._device.set(message)


class KnxYamlNotify(_KnxNotify, KnxYamlEntity):
    """Representation of a KNX notification entity configured from YAML."""

    _device: XknxNotification

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX notification."""
        self._device = XknxNotification(
            knx_module.xknx,
            name=config[CONF_NAME],
            group_address=config[KNX_ADDRESS],
            value_type=config[CONF_TYPE],
        )
        super().__init__(
            knx_module=knx_module,
            unique_id=build_yaml_unique_id(self._device.remote_value.group_address),
            entity_config=config,
        )


class KnxUiNotify(_KnxNotify, KnxUiEntity):
    """Representation of a KNX notification entity configured from UI."""

    _device: XknxNotification

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: ConfigType
    ) -> None:
        """Initialize a KNX notification."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxNotification(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            group_address=knx_conf.get_write(CONF_GA_SEND),
            value_type=knx_conf.get_dpt(CONF_GA_SEND),
        )
