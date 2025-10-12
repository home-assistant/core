"""Support for KNX sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial

from xknx import XKNX
from xknx.core.connection_state import XknxConnectionState, XknxConnectionType
from xknx.devices import Device as XknxDevice, Sensor as XknxSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    RestoreSensor,
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util.enum import try_parse_enum

from .const import ATTR_SOURCE, KNX_MODULE_KEY
from .entity import KnxYamlEntity
from .knx_module import KNXModule
from .schema import SensorSchema

SCAN_INTERVAL = timedelta(seconds=10)


@dataclass(frozen=True)
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
        entity_registry_enabled_default=False,
        force_update=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_incoming,
    ),
    KNXSystemEntityDescription(
        key="telegrams_incoming_error",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_incoming_error,
    ),
    KNXSystemEntityDescription(
        key="telegrams_outgoing",
        entity_registry_enabled_default=False,
        force_update=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_outgoing,
    ),
    KNXSystemEntityDescription(
        key="telegrams_outgoing_error",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda knx: knx.xknx.connection_manager.cemi_count_outgoing_error,
    ),
    KNXSystemEntityDescription(
        key="telegram_count",
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    entities: list[SensorEntity] = []
    entities.extend(
        KNXSystemSensor(knx_module, description)
        for description in SYSTEM_ENTITY_DESCRIPTIONS
    )
    config: list[ConfigType] | None = knx_module.config_yaml.get(Platform.SENSOR)
    if config:
        entities.extend(
            KNXSensor(knx_module, entity_config) for entity_config in config
        )
    async_add_entities(entities)


def _create_sensor(xknx: XKNX, config: ConfigType) -> XknxSensor:
    """Return a KNX sensor to be used within XKNX."""
    return XknxSensor(
        xknx,
        name=config[CONF_NAME],
        group_address_state=config[SensorSchema.CONF_STATE_ADDRESS],
        sync_state=config[SensorSchema.CONF_SYNC_STATE],
        always_callback=True,
        value_type=config[CONF_TYPE],
    )


class KNXSensor(KnxYamlEntity, RestoreSensor):
    """Representation of a KNX sensor."""

    _device: XknxSensor

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize of a KNX sensor."""
        super().__init__(
            knx_module=knx_module,
            device=_create_sensor(knx_module.xknx, config),
        )
        if device_class := config.get(CONF_DEVICE_CLASS):
            self._attr_device_class = device_class
        else:
            self._attr_device_class = try_parse_enum(
                SensorDeviceClass, self._device.ha_device_class()
            )

        self._attr_force_update = config[SensorSchema.CONF_ALWAYS_CALLBACK]
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.sensor_value.group_address_state)
        self._attr_native_unit_of_measurement = self._device.unit_of_measurement()
        self._attr_state_class = config.get(CONF_STATE_CLASS)
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            self._attr_native_value = last_state.state
            self._attr_extra_state_attributes.update(last_state.attributes)
        await super().async_added_to_hass()

    def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self._attr_native_value = self._device.resolve_state()
        if telegram := self._device.last_telegram:
            self._attr_extra_state_attributes[ATTR_SOURCE] = str(
                telegram.source_address
            )
        super().after_update_callback(device)


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

    def after_update_callback(self, device: XknxConnectionState) -> None:
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
