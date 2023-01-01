"""Support for KNX/IP sensors."""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from xknx import XKNX
from xknx.devices import Sensor as XknxSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType

from .const import ATTR_SOURCE, DATA_KNX_CONFIG, DOMAIN
from .knx_entity import KnxEntity
from .schema import SensorSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor(s) for KNX platform."""
    xknx: XKNX = hass.data[DOMAIN].xknx
    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG][Platform.SENSOR]

    async_add_entities(KNXSensor(xknx, entity_config) for entity_config in config)


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


class KNXSensor(KnxEntity, SensorEntity):
    """Representation of a KNX sensor."""

    _device: XknxSensor

    def __init__(self, xknx: XKNX, config: ConfigType) -> None:
        """Initialize of a KNX sensor."""
        super().__init__(_create_sensor(xknx, config))
        if device_class := config.get(CONF_DEVICE_CLASS):
            self._attr_device_class = device_class
        else:
            with suppress(ValueError):
                self._attr_device_class = SensorDeviceClass(
                    str(self._device.ha_device_class())
                )
        self._attr_force_update = self._device.always_callback
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.sensor_value.group_address_state)
        self._attr_native_unit_of_measurement = self._device.unit_of_measurement()
        self._attr_state_class = config.get(CONF_STATE_CLASS)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.resolve_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        attr: dict[str, Any] = {}

        if self._device.last_telegram is not None:
            attr[ATTR_SOURCE] = str(self._device.last_telegram.source_address)
        return attr
