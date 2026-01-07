"""Support for KNX date entities."""

from __future__ import annotations

from datetime import date as dt_date
from typing import Any

from xknx.devices import DateDevice as XknxDateDevice
from xknx.dpt.dpt_11 import KNXDate as XKNXDate

from homeassistant import config_entries
from homeassistant.components.date import DateEntity
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
from .storage.const import CONF_ENTITY, CONF_GA_DATE
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
        platform=Platform.DATE,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiDate,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.DATE):
        entities.extend(
            KnxYamlDate(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.DATE):
        entities.extend(
            KnxUiDate(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KNXDate(DateEntity, RestoreEntity):
    """Representation of a KNX date."""

    _device: XknxDateDevice

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            not self._device.remote_value.readable
            and (last_state := await self.async_get_last_state()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            self._device.remote_value.value = XKNXDate.from_date(
                dt_date.fromisoformat(last_state.state)
            )

    @property
    def native_value(self) -> dt_date | None:
        """Return the latest value."""
        return self._device.value

    async def async_set_value(self, value: dt_date) -> None:
        """Change the value."""
        await self._device.set(value)


class KnxYamlDate(_KNXDate, KnxYamlEntity):
    """Representation of a KNX date configured from YAML."""

    _device: XknxDateDevice

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX date."""
        super().__init__(
            knx_module=knx_module,
            device=XknxDateDevice(
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


class KnxUiDate(_KNXDate, KnxUiEntity):
    """Representation of a KNX date configured from the UI."""

    _device: XknxDateDevice

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: dict[str, Any]
    ) -> None:
        """Initialize KNX date."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxDateDevice(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            localtime=False,
            group_address=knx_conf.get_write(CONF_GA_DATE),
            group_address_state=knx_conf.get_state_and_passive(CONF_GA_DATE),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
        )
