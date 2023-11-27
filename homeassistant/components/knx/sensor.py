"""Support for KNX/IP sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from xknx import XKNX
from xknx.core.connection_state import XknxConnectionState, XknxConnectionType
from xknx.devices import Sensor as XknxSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    CONF_TYPE,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util.enum import try_parse_enum

from . import KNXModule
from .const import ATTR_SOURCE, DATA_KNX_CONFIG, DOMAIN
from .knx_entity import KnxEntity
from .schema import SensorSchema

SCAN_INTERVAL = timedelta(seconds=10)


@dataclass
class KNXSystemEntityDescription(SensorEntityDescription):
    """Class describing KNX system sensor entities."""

    always_available: bool = True
    entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    has_entity_name: bool = True
    should_poll: bool = True
    value_fn: Callable[[KNXModule], StateType | datetime] = lambda knx: None


SYSTEM_ENTITY_DESCRIPTIONS = (
    KNXSystemEntityDescription(
        key="individual_address",
        always_available=False,
        icon="mdi:router-network",
        should_poll=False,
        value_fn=lambda knx: str(knx.xknx.current_address),
    ),
    KNXSystemEntityDescription(
        key="connected_since",
        always_available=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        should_poll=False,
        value_fn=lambda knx: knx.xknx.connection_manager.connected_since,
    ),
    KNXSystemEntityDescription(
        key="connection_type",
        always_available=False,
        device_class=SensorDeviceClass.ENUM,
        options=[opt.value for opt in XknxConnectionType],
        should_poll=False,
        value_fn=lambda knx: knx.xknx.connection_manager.connection_type.value,
    ),
    KNXSystemEntityDescription(
        key="telegrams_incoming",
        icon="mdi:upload-network",
        entity_registry_enabled_default=False,
        force_update=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_incoming,
    ),
    KNXSystemEntityDescription(
        key="telegrams_incoming_error",
        icon="mdi:help-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_incoming_error,
    ),
    KNXSystemEntityDescription(
        key="telegrams_outgoing",
        icon="mdi:download-network",
        entity_registry_enabled_default=False,
        force_update=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_outgoing,
    ),
    KNXSystemEntityDescription(
        key="telegrams_outgoing_error",
        icon="mdi:close-network",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_outgoing_error,
    ),
    KNXSystemEntityDescription(
        key="telegram_count",
        icon="mdi:plus-network",
        force_update=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_outgoing
        + knx.xknx.connection_manager.cemi_count_incoming
        + knx.xknx.connection_manager.cemi_count_incoming_error,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor(s) for KNX platform."""
    knx_module: KNXModule = hass.data[DOMAIN]

    async_add_entities(
        KNXSystemSensor(knx_module, description)
        for description in SYSTEM_ENTITY_DESCRIPTIONS
    )

    config: list[ConfigType] = hass.data[DATA_KNX_CONFIG].get(Platform.SENSOR)
    if config:
        async_add_entities(
            KNXSensor(knx_module.xknx, entity_config) for entity_config in config
        )


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
            self._attr_device_class = try_parse_enum(
                SensorDeviceClass, self._device.ha_device_class()
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


class KNXSystemSensor(SensorEntity):
    """Representation of a KNX system sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        knx: KNXModule,
        description: KNXSystemEntityDescription,
    ) -> None:
        """Initialize of a KNX system sensor."""
        self.entity_description: KNXSystemEntityDescription = description
        self.knx = knx

        self._attr_device_info = knx.interface_device.device_info
        self._attr_should_poll = description.should_poll
        self._attr_translation_key = description.key
        self._attr_unique_id = f"_{knx.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.knx)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.entity_description.always_available:
            return True
        return self.knx.xknx.connection_manager.state is XknxConnectionState.CONNECTED

    async def after_update_callback(self, _: XknxConnectionState) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self.knx.xknx.connection_manager.register_connection_state_changed_cb(
            self.after_update_callback
        )
        self.async_on_remove(
            partial(
                self.knx.xknx.connection_manager.unregister_connection_state_changed_cb,
                self.after_update_callback,
            )
        )
