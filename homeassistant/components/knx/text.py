"""Support for KNX text entities."""

from __future__ import annotations

from propcache.api import cached_property
from xknx.devices import Notification as XknxNotification
from xknx.dpt import DPTLatin1

from homeassistant import config_entries
from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_MODE,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    DOMAIN,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
)
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .knx_module import KNXModule
from .storage.const import CONF_ENTITY, CONF_GA_TEXT
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up text(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.TEXT,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiText,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.TEXT):
        entities.extend(
            KnxYamlText(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.TEXT):
        entities.extend(
            KnxUiText(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxText(TextEntity, RestoreEntity):
    """Representation of a KNX text."""

    _device: XknxNotification
    _attr_native_max = 14

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if not self._device.remote_value.readable and (
            last_state := await self.async_get_last_state()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._device.remote_value.value = last_state.state

    @cached_property
    def pattern(self) -> str | None:
        """Return the regex pattern that the value must match."""
        return (
            r"[\u0000-\u00ff]*"  # Latin-1
            if issubclass(self._device.remote_value.dpt_class, DPTLatin1)
            else r"[\u0000-\u007f]*"  # ASCII
        )

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return self._device.message

    async def async_set_value(self, value: str) -> None:
        """Change the value."""
        await self._device.set(value)


class KnxYamlText(_KnxText, KnxYamlEntity):
    """Representation of a KNX text configured from YAML."""

    _device: XknxNotification

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX text."""
        super().__init__(
            knx_module=knx_module,
            device=XknxNotification(
                knx_module.xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                group_address_state=config.get(CONF_STATE_ADDRESS),
                respond_to_read=config[CONF_RESPOND_TO_READ],
                value_type=config[CONF_TYPE],
            ),
        )
        self._attr_mode = config[CONF_MODE]
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.remote_value.group_address)


class KnxUiText(_KnxText, KnxUiEntity):
    """Representation of a KNX text configured from UI."""

    _device: XknxNotification

    def __init__(
        self,
        knx_module: KNXModule,
        unique_id: str,
        config: ConfigType,
    ) -> None:
        """Initialize a KNX text."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxNotification(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            group_address=knx_conf.get_write(CONF_GA_TEXT),
            group_address_state=knx_conf.get_state_and_passive(CONF_GA_TEXT),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
            value_type=knx_conf.get_dpt(CONF_GA_TEXT),
        )
        self._attr_mode = TextMode(knx_conf.get(CONF_MODE))
