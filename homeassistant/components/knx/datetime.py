"""Support for KNX/IP datetime."""

from __future__ import annotations

from datetime import datetime

from xknx import XKNX
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import KNXModule
from .const import (
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
)
from .entity import KnxYamlEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.DATETIME]

    async_add_entities(
        KNXDateTimeEntity(knx_module, entity_config) for entity_config in config
    )


def _create_xknx_device(xknx: XKNX, config: ConfigType) -> XknxDateTimeDevice:
    """Return a XKNX DateTime object to be used within XKNX."""
    return XknxDateTimeDevice(
        xknx,
        name=config[CONF_NAME],
        localtime=False,
        group_address=config[KNX_ADDRESS],
        group_address_state=config.get(CONF_STATE_ADDRESS),
        respond_to_read=config[CONF_RESPOND_TO_READ],
        sync_state=config[CONF_SYNC_STATE],
    )


class KNXDateTimeEntity(KnxYamlEntity, DateTimeEntity, RestoreEntity):
    """Representation of a KNX datetime."""

    _device: XknxDateTimeDevice

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX time."""
        super().__init__(
            knx_module=knx_module,
            device=_create_xknx_device(knx_module.xknx, config),
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.remote_value.group_address)

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
