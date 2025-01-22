"""Support for KNX/IP sensors."""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any

import voluptuous as vol
from xknx import XKNX
from xknx.core.connection_state import XknxConnectionState, XknxConnectionType
from xknx.devices import Sensor as XknxSensor
from xknx.dpt import DPTBase, DPTNumeric, DPTString

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
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util.enum import try_parse_enum

from .const import ATTR_SOURCE, CONF_SYNC_STATE, KNX_MODULE_KEY
from .entity import (
    BasePlatformConfiguration,
    KnxUiEntity,
    KnxUiEntityPlatformController,
    KnxYamlEntity,
    StorageSerialization,
)
from .knx_module import KNXModule
from .models import GroupAddressConfig
from .schema import (
    ConfigGroupSchema,
    DatapointTypeSchema,
    EntityConfigGroupSchema,
    GroupAddressConfigSchema,
    PlatformConfigSchema,
    SensorSchema,
    SyncStateSchema,
)
from .storage.const import CONF_ALWAYS_CALLBACK, CONF_DEVICE_INFO, CONF_GA_SENSOR

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
    knx_module: KNXModule = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()

    knx_module.config_store.add_platform(
        Platform.SENSOR,
        KnxUiSensorPlatformController(knx_module, platform, UiSensorEntity),
    )

    system_sensors: Iterator[KNXSystemSensor] = (
        KNXSystemSensor(knx_module, desc) for desc in SYSTEM_ENTITY_DESCRIPTIONS
    )
    yaml_sensors: Iterator[SensorEntity] = (
        KNXSensor(knx_module, entity_config)
        for entity_config in knx_module.config_yaml.get(Platform.SENSOR, [])
    )
    ui_sensors: Iterator[UiSensorEntity] = (
        UiSensorEntity(
            knx_module,
            uid,
            UiSensorConfig.from_storage_dict(cfg),
        )
        for uid, cfg in knx_module.config_store.data["entities"]
        .get(Platform.SENSOR, {})
        .items()
    )

    async_add_entities([*system_sensors, *yaml_sensors, *ui_sensors])


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


class KNXSensor(KnxYamlEntity, SensorEntity):
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

        self._attr_force_update = self._device.always_callback
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.sensor_value.group_address_state)
        self._attr_native_unit_of_measurement = self._device.unit_of_measurement()
        self._attr_state_class = config.get(CONF_STATE_CLASS)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.resolve_state() or None

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


@dataclass
class SensorConfig(BasePlatformConfiguration, ABC):
    """Base configuration data class for a sensor entity.

    Provides core sensor-related fields. Subclasses must implement
    how these fields map to/from a schema (via `to_dict`/`from_dict`)
    and may add additional sensor-specific logic.
    """

    sensor_ga: GroupAddressConfig
    state_class: SensorStateClass | None
    device_class: SensorDeviceClass | None
    always_callback: bool | None
    sync_state: int | str | bool | None
    name: str | None
    device_info: str | None
    entity_category: EntityCategory | None


@dataclass
class UiSensorConfig(SensorConfig, StorageSerialization):
    """UI-oriented sensor configuration with storage serialization.

    Extends `BaseSensorConfig` to define how the sensor configuration
    is validated and serialized for a UI environment. Also includes
    methods for storing/loading from a dictionary (via
    `StorageSerializationMixin`).
    """

    @classmethod
    def get_schema(cls) -> PlatformConfigSchema:
        """Retrieve the Voluptuous-based UI schema for this sensor configuration.

        Returns:
            PlatformConfigSchema: A schema describing valid fields, types,
            and optional advanced settings for sensor entities.

        """
        return PlatformConfigSchema(
            str(Platform.SENSOR),
            vol.Schema(
                {
                    vol.Required("platform_config"): ConfigGroupSchema(
                        vol.Schema(
                            {
                                vol.Required(CONF_GA_SENSOR): GroupAddressConfigSchema(
                                    write=False,
                                    state_required=True,
                                    allowed_dpts=DatapointTypeSchema.derive_subtypes(
                                        DPTNumeric, DPTString
                                    ),
                                ),
                                vol.Optional(CONF_STATE_CLASS, default=None): vol.Maybe(
                                    vol.Coerce(SensorStateClass)
                                ),
                                vol.Optional(
                                    CONF_DEVICE_CLASS, default=None
                                ): vol.Maybe(vol.Coerce(SensorDeviceClass)),
                                vol.Optional("advanced"): ConfigGroupSchema(
                                    vol.Schema(
                                        {
                                            vol.Optional(
                                                CONF_ALWAYS_CALLBACK, default=False
                                            ): bool,
                                            vol.Optional(
                                                CONF_SYNC_STATE, default=True
                                            ): SyncStateSchema(),
                                        }
                                    ),
                                    {"collapsible": True, "collapsed": True},
                                ),
                            }
                        )
                    ),
                    vol.Required("entity_config"): EntityConfigGroupSchema(
                        allowed_categories=(EntityCategory.DIAGNOSTIC,)
                    ),
                }
            ),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UiSensorConfig:
        """Instantiate this configuration from a UI-compatible dictionary.

        The dictionary is validated via `SensorConfigSchema`, then
        parsed to fill the sensor's fields. If validation fails, an
        error is raised (e.g., by Voluptuous).

        Args:
            data (dict[str, Any]): A dictionary adhering to `get_schema()`.

        Returns:
            UiSensorConfig: A new sensor configuration instance
            reflecting the UI data.

        """

        validated = cls.get_schema()(data)
        config = validated["config"]

        category = config["entity_config"].get(CONF_ENTITY_CATEGORY)
        state_class = config["platform_config"].get(CONF_STATE_CLASS)
        device_class = config["platform_config"].get(CONF_DEVICE_CLASS)

        # Construct the instance using validated data
        return cls(
            sensor_ga=GroupAddressConfig.from_dict(
                config["platform_config"][CONF_GA_SENSOR]
            ),
            state_class=SensorStateClass(state_class) if state_class else None,
            device_class=SensorDeviceClass(device_class) if device_class else None,
            always_callback=config["platform_config"]
            .get("advanced")
            .get(CONF_ALWAYS_CALLBACK),
            sync_state=config["platform_config"].get("advanced").get(CONF_SYNC_STATE),
            name=config["entity_config"].get(CONF_NAME),
            device_info=config["entity_config"].get(CONF_DEVICE_INFO),
            entity_category=EntityCategory(category) if category else None,
        )

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> UiSensorConfig:
        """Instantiate this configuration from a serialized dictionary in the storage format.

        Args:
            data (dict[str, Any]): A dictionary adhering to the storage format.

        Returns:
            UiSensorConfig: A new sensor configuration instance
            reflecting the serialized data.

        """

        device_class = data.get(CONF_DEVICE_CLASS)
        state_class = data.get(CONF_STATE_CLASS)
        entity_category = data.get(CONF_ENTITY_CATEGORY)

        return UiSensorConfig(
            sensor_ga=GroupAddressConfig.from_dict(data[CONF_GA_SENSOR]),
            state_class=SensorStateClass(state_class) if state_class else None,
            device_class=SensorDeviceClass(device_class) if device_class else None,
            always_callback=data.get(CONF_ALWAYS_CALLBACK),
            sync_state=data.get(CONF_SYNC_STATE),
            name=data.get(CONF_NAME),
            device_info=data.get(CONF_DEVICE_INFO),
            entity_category=EntityCategory(entity_category)
            if entity_category
            else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert this sensor configuration into a UI-friendly dictionary.

        Builds a dictionary that matches the format expected by the UI schema
        returned by `get_schema()` (e.g., grouping platform and entity config).

        Returns:
            dict[str, Any]: A dictionary representation aligned with the
            sensor UI schema.

        """

        result: dict[str, Any] = {
            "platform": "sensor",
            "config": {
                "platform_config": {
                    CONF_GA_SENSOR: self.sensor_ga.to_dict(),
                    "advanced": {},
                },
                "entity_config": {},
            },
        }

        # Platform-specific fields
        if self.state_class is not None:
            result["config"]["platform_config"][CONF_STATE_CLASS] = self.state_class
        if self.device_class is not None:
            result["config"]["platform_config"][CONF_DEVICE_CLASS] = self.device_class

        # Advanced subfields
        if self.always_callback is not None:
            result["config"]["platform_config"]["advanced"][CONF_ALWAYS_CALLBACK] = (
                self.always_callback
            )
        if self.sync_state is not None:
            result["config"]["platform_config"]["advanced"][CONF_SYNC_STATE] = (
                self.sync_state
            )

        # Entity config
        if self.name is not None:
            result["config"]["entity_config"][CONF_NAME] = self.name
        if self.device_info is not None:
            result["config"]["entity_config"][CONF_DEVICE_INFO] = self.device_info
        if self.entity_category is not None:
            result["config"]["entity_config"][CONF_ENTITY_CATEGORY] = (
                self.entity_category
            )

        # Validate before returning to set defaults
        return self.get_schema()(result)

    def to_storage_dict(self) -> dict[str, Any]:
        """Convert the current instance into a dictionary suitable for storage."""

        return {
            CONF_GA_SENSOR: self.sensor_ga.to_dict(),
            CONF_STATE_CLASS: self.state_class,
            CONF_DEVICE_CLASS: self.device_class,
            CONF_ALWAYS_CALLBACK: self.always_callback,
            CONF_SYNC_STATE: self.sync_state,
            CONF_NAME: self.name,
            CONF_DEVICE_INFO: self.device_info,
            CONF_ENTITY_CATEGORY: self.entity_category,
        }


class KnxUiSensorPlatformController(KnxUiEntityPlatformController):
    """Class to manage dynamic adding and reloading of UI entities."""

    async def create_entity(self, unique_id: str, config: dict[str, Any]) -> None:
        """Add a new UI entity."""

        sensorConfig = UiSensorConfig.from_storage_dict(config)
        sensor = UiSensorEntity(self._knx_module, unique_id, sensorConfig)
        await self._entity_platform.async_add_entities([sensor])


class BaseSensorEntity(SensorEntity):
    """Base class for a KNX sensor."""

    _device: XknxSensor

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._device.resolve_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return device specific state attributes."""
        if self._device.last_telegram is not None:
            return {
                ATTR_SOURCE: str(self._device.last_telegram.source_address),
            }
        return None


class UiSensorEntity(BaseSensorEntity, KnxUiEntity):
    """Representation of a KNX sensor."""

    _device: XknxSensor

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: SensorConfig
    ) -> None:
        """Initialize of a KNX sensor."""
        super().__init__(knx_module, unique_id, {})

        if config.sensor_ga.dpt is None:
            raise ValueError("DPT must be provided for sensor entity")

        dpt = DPTBase.parse_transcoder(
            {"main": config.sensor_ga.dpt.main, "sub": config.sensor_ga.dpt.sub}
        )
        if dpt is None:
            raise ValueError(f"Could not parse DPT for data: {config.sensor_ga.dpt}")

        name = config.name or ""
        always_callback = config.always_callback or False
        sync_state = config.sync_state or True

        self._device = XknxSensor(
            xknx=knx_module.xknx,
            name=name,
            group_address_state=config.sensor_ga.state_ga,
            sync_state=sync_state,
            always_callback=always_callback,
            value_type=dpt.value_type,
        )

        self._attr_name = name
        self._attr_device_class = config.device_class
        self._attr_force_update = always_callback
        self._attr_entity_category = config.entity_category
        self._attr_state_class = config.state_class
        self._attr_unique_id = unique_id
        self._attr_native_unit_of_measurement = self._device.unit_of_measurement()
