"""Support for KNX/IP switches."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import Switch as XknxSwitch

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import CONF_RESPOND_TO_READ, DATA_KNX_CONFIG, DOMAIN, KNX_ADDRESS
from .knx_entity import KnxEntity
from .schema import SwitchSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch(es) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][Platform.SWITCH]

    async_add_entities(KNXSwitch(xknx, entity_config) for entity_config in config)


class KNXSwitch(KnxEntity, SwitchEntity, RestoreEntity):
    """Representation of a KNX switch."""

    _device: XknxSwitch

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX switch."""
        super().__init__(
            device=XknxSwitch(
                xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                group_address_state=config.get(SwitchSchema.CONF_STATE_ADDRESS),
                respond_to_read=config[CONF_RESPOND_TO_READ],
                invert=config[SwitchSchema.CONF_INVERT],
            )
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_unique_id = str(self._device.switch.group_address)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if not self._device.switch.readable and (
            last_state := await self.async_get_last_state()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._device.switch.value = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self._device.state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._device.set_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._device.set_off()
