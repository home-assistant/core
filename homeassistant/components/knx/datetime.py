"""Support for KNX datetime entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from xknx.devices import DateTimeDevice as XknxDateTimeDevice
from xknx.dpt.dpt_19 import KNXDateTime as XKNXDateTime

from homeassistant import config_entries
from homeassistant.components.datetime import DateTimeEntity
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
from homeassistant.util import dt as dt_util

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
from .storage.const import CONF_ENTITY, CONF_GA_DATETIME
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
        platform=Platform.DATETIME,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiDateTime,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.DATETIME):
        entities.extend(
            KnxYamlDateTime(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.DATETIME):
        entities.extend(
            KnxUiDateTime(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KNXDateTime(DateTimeEntity, RestoreEntity):
    """Representation of a KNX datetime."""

    _device: XknxDateTimeDevice

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            not self._device.remote_value.readable
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self._device.remote_value.value = XKNXDateTime.from_datetime(
                datetime.fromisoformat(last_state.state).astimezone(
                    dt_util.get_default_time_zone()
                )
            )

    @property
    def native_value(self) -> datetime | None:
        """Return the latest value."""
        if (naive_dt := self._device.value) is None:
            return None
        return naive_dt.replace(tzinfo=dt_util.get_default_time_zone())

    async def async_set_value(self, value: datetime) -> None:
        """Change the value."""
        await self._device.set(value.astimezone(dt_util.get_default_time_zone()))


class KnxYamlDateTime(_KNXDateTime, KnxYamlEntity):
    """Representation of a KNX datetime configured from YAML."""

    _device: XknxDateTimeDevice

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX datetime."""
        super().__init__(
            knx_module=knx_module,
            device=XknxDateTimeDevice(
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


class KnxUiDateTime(_KNXDateTime, KnxUiEntity):
    """Representation of a KNX datetime configured from the UI."""

    _device: XknxDateTimeDevice

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize KNX datetime."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxDateTimeDevice(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            localtime=False,
            group_address=knx_conf.get_write(CONF_GA_DATETIME),
            group_address_state=knx_conf.get_state_and_passive(CONF_GA_DATETIME),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
        )
