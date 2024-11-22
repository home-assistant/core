"""Support for KNX/IP date."""

from __future__ import annotations

from datetime import date as dt_date

from xknx import XKNX
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.DATE]

    async_add_entities(
        KNXDateEntity(knx_module, entity_config) for entity_config in config
    )


def _create_xknx_device(xknx: XKNX, config: ConfigType) -> XknxDateDevice:
    """Return a XKNX DateTime object to be used within XKNX."""
    return XknxDateDevice(
        xknx,
        name=config[CONF_NAME],
        localtime=False,
        group_address=config[KNX_ADDRESS],
        group_address_state=config.get(CONF_STATE_ADDRESS),
        respond_to_read=config[CONF_RESPOND_TO_READ],
        sync_state=config[CONF_SYNC_STATE],
    )


class KNXDateEntity(KnxYamlEntity, DateEntity, RestoreEntity):
    """Representation of a KNX date."""

    _device: XknxDateDevice

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
