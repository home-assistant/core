"""Support for KNX/IP binary sensors."""
from __future__ import annotations

from typing import Any

from xknx import XKNX
from xknx.devices import BinarySensor as XknxBinarySensor

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt

from .const import ATTR_COUNTER, ATTR_LAST_KNX_UPDATE, ATTR_SOURCE, DOMAIN
from .knx_entity import KnxEntity
from .schema import BinarySensorSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up binary sensor(s) for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return

    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    async_add_entities(
        KNXBinarySensor(xknx, entity_config) for entity_config in platform_config
    )


class KNXBinarySensor(KnxEntity, BinarySensorEntity):
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
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_force_update = self._device.ignore_internal_state
        self._attr_unique_id = str(self._device.remote_value.group_address_state)

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
            attr[ATTR_LAST_KNX_UPDATE] = str(
                dt.as_utc(self._device.last_telegram.timestamp)
            )
        return attr
