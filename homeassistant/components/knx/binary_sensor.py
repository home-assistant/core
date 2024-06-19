"""Support for KNX/IP binary sensors."""

from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import BinarySensor as XknxBinarySensor

from homeassistant import config_entries
from homeassistant.components.binary_sensor import BinarySensorEntity
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

from .const import ATTR_COUNTER, ATTR_SOURCE, DATA_KNX_CONFIG, DOMAIN
from .knx_entity import KnxEntity
from .schema import BinarySensorSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KNX binary sensor platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: ConfigType = hass.data[DATA_KNX_CONFIG]

    async_add_entities(
        KNXBinarySensor(xknx, entity_config)
        for entity_config in config[Platform.BINARY_SENSOR]
    )


class KNXBinarySensor(KnxEntity, BinarySensorEntity, RestoreEntity):
    """Representation of a KNX binary sensor."""

    _device: XknxBinarySensor

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of KNX binary sensor."""
        super().__init__(
            device=XknxBinarySensor(
                xknx,
                name=config[CONF_NAME],
                group_address_state=config[BinarySensorSchema.CONF_STATE_ADDRESS],
                invert=config[BinarySensorSchema.CONF_INVERT],
                sync_state=config[BinarySensorSchema.CONF_SYNC_STATE],
                ignore_internal_state=config[
                    BinarySensorSchema.CONF_IGNORE_INTERNAL_STATE
                ],
                context_timeout=config.get(BinarySensorSchema.CONF_CONTEXT_TIMEOUT),
                reset_after=config.get(BinarySensorSchema.CONF_RESET_AFTER),
            )
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_force_update = self._device.ignore_internal_state
        self._attr_unique_id = str(self._device.remote_value.group_address_state)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            await self._device.remote_value.update_value(last_state.state == STATE_ON)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._device.is_on()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.counter is not None:
            attr[ATTR_COUNTER] = self._device.counter
        if self._device.last_telegram is not None:
            attr[ATTR_SOURCE] = str(self._device.last_telegram.source_address)
        return attr
