"""Support for KNX time entities."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any

from xknx.devices import TimeDevice as XknxTimeDevice
from xknx.dpt.dpt_10 import KNXTime as XknxTime

from homeassistant import config_entries
from homeassistant.components.time import TimeEntity
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
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
from .storage.const import CONF_ENTITY, CONF_GA_TIME
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.TIME,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiTime,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.TIME):
        entities.extend(
            KnxYamlTime(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.TIME):
        entities.extend(
            KnxUiTime(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KNXTime(TimeEntity, RestoreEntity):
    """Representation of a KNX time."""

    _device: XknxTimeDevice

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            not self._device.remote_value.readable
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self._device.remote_value.value = XknxTime.from_time(
                dt_time.fromisoformat(last_state.state)
            )

    @property
    def native_value(self) -> dt_time | None:
        """Return the latest value."""
        return self._device.value

    async def async_set_value(self, value: dt_time) -> None:
        """Change the value."""
        await self._device.set(value)


class KnxYamlTime(_KNXTime, KnxYamlEntity):
    """Representation of a KNX time configured from YAML."""

    _device: XknxTimeDevice

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX time."""
        super().__init__(
            knx_module=knx_module,
            device=XknxTimeDevice(
                knx_module.xknx,
                name=config[CONF_NAME],
                localtime=False,
                group_address=config[KNX_ADDRESS],
                group_address_state=config.get(CONF_STATE_ADDRESS),
                respond_to_read=config[CONF_RESPOND_TO_READ],
                sync_state=config[CONF_SYNC_STATE],
            ),
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.remote_value.group_address)


class KnxUiTime(_KNXTime, KnxUiEntity):
    """Representation of a KNX time configured from the UI."""

    _device: XknxTimeDevice

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize KNX time."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxTimeDevice(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            localtime=False,
            group_address=knx_conf.get_write(CONF_GA_TIME),
            group_address_state=knx_conf.get_state_and_passive(CONF_GA_TIME),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
        )
