"""Support for KNX/IP sensors."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable

from xknx import XKNX
from xknx.devices import Sensor as XknxSensor

from homeassistant.components.sensor import DEVICE_CLASSES, SensorEntity
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util import dt

from .const import ATTR_LAST_KNX_UPDATE, ATTR_SOURCE, DOMAIN
from .knx_entity import KnxEntity
from .schema import SensorSchema


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable[[Iterable[Entity]], None],
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up sensor(s) for KNX platform."""
    if not discovery_info or not discovery_info["platform_config"]:
        return

    platform_config = discovery_info["platform_config"]
    xknx: XKNX = hass.data[DOMAIN].xknx

    entities = []
    for entity_config in platform_config:
        entities.append(KNXSensor(xknx, entity_config))

    async_add_entities(entities)


class KNXSensor(KnxEntity, SensorEntity):
    """Representation of a KNX sensor."""

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of a KNX sensor."""
        self._device: XknxSensor
        super().__init__(self._create_sensor(xknx, config))

    @staticmethod
    def _create_sensor(xknx: XKNX, config: ConfigType) -> XknxSensor:
        """Return a KNX sensor to be used within XKNX."""
        return XknxSensor(
            xknx,
            name=config[CONF_NAME],
            group_address_state=config[SensorSchema.CONF_STATE_ADDRESS],
            sync_state=config[SensorSchema.CONF_SYNC_STATE],
            always_callback=config[SensorSchema.CONF_ALWAYS_CALLBACK],
            value_type=config[CONF_TYPE],
        )

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.resolve_state()

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        return self._device.unit_of_measurement()

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        device_class = self._device.ha_device_class()
        if device_class in DEVICE_CLASSES:
            return device_class
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.last_telegram is not None:
            attr[ATTR_SOURCE] = str(self._device.last_telegram.source_address)
            attr[ATTR_LAST_KNX_UPDATE] = str(
                dt.as_utc(self._device.last_telegram.timestamp)
            )
        return attr

    @property
    def force_update(self) -> bool:
        """
        Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return self._device.always_callback
