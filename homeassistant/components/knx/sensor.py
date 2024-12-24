"""Support for KNX/IP sensors."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType, StateType
from homeassistant.util.enum import try_parse_enum

from . import KNXModule
from .const import ATTR_SOURCE, DOMAIN, KNX_MODULE_KEY
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .light import CONF_GA_STATE, CONF_SYNC_STATE
from .schema import SensorSchema
from .storage.const import CONF_ALWAYS_CALLBACK, CONF_DEVICE_INFO, CONF_ENTITY
from .storage.entity_store_schema import CONF_GA_SENSOR, CONF_VALUE_TYPE

SCAN_INTERVAL = timedelta(seconds=10)


@dataclass(frozen=True)
class KNXSystemEntityDescription(SensorEntityDescription):
    """Class describing KNX system sensor entities."""

    always_available: bool = True
    entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    has_entity_name: bool = True
    should_poll: bool = True
    value_fn: Callable[[KNXModule], StateType | datetime | None] = lambda knx: None


SYSTEM_ENTITY_DESCRIPTIONS: tuple[KNXSystemEntityDescription, ...] = (
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
        value_fn=lambda knx: (
            knx.xknx.connection_manager.cemi_count_outgoing
            + knx.xknx.connection_manager.cemi_count_incoming
            + knx.xknx.connection_manager.cemi_count_incoming_error
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KNX platform sensors."""
    knx_module: KNXModule = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()

    knx_module.config_store.add_platform(
        Platform.SENSOR,
        KnxUiSensorPlatformController(knx_module, platform, KnxUiSensor),
    )

    system_sensors: Iterator[KNXSystemSensor] = (
        KNXSystemSensor(knx_module, desc) for desc in SYSTEM_ENTITY_DESCRIPTIONS
    )
    yaml_sensors: Iterator[KnxYamlSensor] = (
        KnxYamlSensor(KnxSensorDescriptionFactory.create_from_yaml(knx_module, config))
        for config in knx_module.config_yaml.get(Platform.SENSOR, [])
    )
    ui_sensors: Iterator[KnxUiSensor] = (
        KnxUiSensor(
            KnxSensorDescriptionFactory.create_from_ui(knx_module, uid, cfg),
        )
        for uid, cfg in knx_module.config_store.data["entities"]
        .get(Platform.SENSOR, {})
        .items()
    )

    async_add_entities([*system_sensors, *yaml_sensors, *ui_sensors])


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
        self.knx: KNXModule = knx

        self._attr_device_info = knx.interface_device.device_info
        self._attr_should_poll = description.should_poll
        self._attr_translation_key = description.key
        self._attr_unique_id = f"_{knx.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.knx)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.entity_description.always_available:
            return True
        return self.knx.xknx.connection_manager.state is XknxConnectionState.CONNECTED

    def after_update_callback(self, _: XknxConnectionState) -> None:
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


class KnxSensor(SensorEntity):
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


class KnxUiSensor(KnxSensor, KnxUiEntity):
    """Representation of a KNX sensor configured from UI with new description."""

    _device: XknxSensor

    def __init__(self, description: KnxSensorDescription) -> None:
        """Initialize of a KNX sensor."""
        self.entity_description: KnxSensorDescription = description
        self._device = description.device

        super().__init__(description.xknx_module, description.key, {})
        self._attr_device_info = description.device_info


class KnxYamlSensor(KnxSensor, KnxYamlEntity):
    """Representation of a KNX sensor configured from YAML with new description."""

    _device: XknxSensor

    def __init__(self, description: KnxSensorDescription) -> None:
        """Initialize of a KNX sensor."""

        super().__init__(description.xknx_module, description.device)
        self.entity_description: KnxSensorDescription = description
        self._attr_unique_id = description.key


@dataclass(frozen=True, kw_only=True)
class KnxSensorDescription(SensorEntityDescription):
    """Class describing KNX system sensor entities."""

    device: XknxSensor
    xknx_module: KNXModule
    device_info: DeviceInfo | None = None


class KnxSensorDescriptionFactory:
    """Factory class to create KNX sensor descriptions for Home Assistant."""

    @staticmethod
    def _build_description(
        xknx_module: KNXModule,
        *,
        key: str,
        name: str,
        group_address_state: str,
        sync_state: bool,
        always_callback: bool,
        value_type: str,
        state_class: str | None = None,
        entity_category: str | None = None,
        device_class: str | None = None,
        device_info: str | None = None,
    ) -> KnxSensorDescription:
        """Instantiate a KnxSensorDescription object.

        Args:
            xknx_module: The KNXModule instance.
            key: A unique identifier for the entity.
            name: The sensor's display name.
            group_address_state: The KNX group address used for state updates.
            sync_state: Whether the sensor should sync state immediately on startup.
            always_callback: If True, the sensor always triggers an update callback.
            value_type: The type of the sensor (e.g., temperature, humidity).
            state_class: The Home Assistant SensorStateClass, if any.
            entity_category: The Home Assistant EntityCategory, if any.
            device_class: The Home Assistant SensorDeviceClass, if any.
            device_info: Additional device information if available.

        Returns:
            A fully configured KnxSensorDescription instance.

        """

        device = XknxSensor(
            xknx=xknx_module.xknx,
            name=name,
            group_address_state=group_address_state,
            sync_state=sync_state,
            always_callback=always_callback,
            value_type=value_type,
        )

        _state_class: SensorStateClass | None = (
            SensorStateClass(state_class) if state_class else None
        )

        _entity_category: EntityCategory | None = (
            EntityCategory(entity_category) if entity_category else None
        )

        _device_class: SensorDeviceClass | None = (
            SensorDeviceClass(device_class) if device_class else None
        )

        if not _device_class:
            _device_class = try_parse_enum(SensorDeviceClass, device.ha_device_class())

        _device_info: DeviceInfo | None = (
            DeviceInfo(identifiers={(DOMAIN, device_info)}) if device_info else None
        )

        return KnxSensorDescription(
            key=key,
            xknx_module=xknx_module,
            device=device,
            force_update=device.always_callback,
            native_unit_of_measurement=device.unit_of_measurement(),
            state_class=_state_class,
            entity_category=_entity_category,
            device_class=_device_class,
            device_info=_device_info,
        )

    @staticmethod
    def create_from_yaml(
        xknx_module: KNXModule, config: ConfigType
    ) -> KnxSensorDescription:
        """Create a KnxSensorDescription from a YAML-based configuration.

        Args:
            xknx_module: The KNXModule instance.
            config: A dict-like configuration object that follows the YAML schema.

        Returns:
            A KnxSensorDescription instance.

        """
        return KnxSensorDescriptionFactory._build_description(
            xknx_module=xknx_module,
            key=str(config[SensorSchema.CONF_STATE_ADDRESS]),
            name=config[CONF_NAME],
            group_address_state=config[SensorSchema.CONF_STATE_ADDRESS],
            sync_state=config[SensorSchema.CONF_SYNC_STATE],
            always_callback=config[SensorSchema.CONF_ALWAYS_CALLBACK],
            value_type=config[CONF_TYPE],
            state_class=config.get(CONF_STATE_CLASS),
            entity_category=config.get(CONF_ENTITY_CATEGORY),
            device_class=config.get(CONF_DEVICE_CLASS),
        )

    @staticmethod
    def create_from_ui(
        xknx_module: KNXModule, uid: str, config: ConfigType
    ) -> KnxSensorDescription:
        """Create a KnxSensorDescription from a UI-based configuration.

        Args:
            xknx_module: The KNXModule instance.
            uid: A unique identifier for this UI-configured entity.
            config: A dict-like configuration object that contains domain and entity settings.

        Returns:
            A KnxSensorDescription instance.

        """
        domain_conf = config[DOMAIN]
        entity_conf = config[CONF_ENTITY]

        return KnxSensorDescriptionFactory._build_description(
            xknx_module=xknx_module,
            key=uid,
            name=entity_conf[CONF_NAME],
            group_address_state=domain_conf[CONF_GA_SENSOR][CONF_GA_STATE],
            sync_state=domain_conf[CONF_SYNC_STATE],
            always_callback=domain_conf[CONF_ALWAYS_CALLBACK],
            value_type=domain_conf[CONF_VALUE_TYPE],
            state_class=entity_conf.get(CONF_STATE_CLASS),
            entity_category=entity_conf.get(CONF_ENTITY_CATEGORY),
            device_class=entity_conf.get(CONF_DEVICE_CLASS),
            device_info=entity_conf.get(CONF_DEVICE_INFO),
        )


class KnxUiSensorPlatformController(KnxUiEntityPlatformController):
    """Class to manage dynamic adding and reloading of UI entities."""

    async def create_entity(self, unique_id: str, config: dict[str, Any]) -> None:
        """Add a new UI entity."""
        description = KnxSensorDescriptionFactory.create_from_ui(
            self._knx_module, unique_id, config
        )
        sensor = KnxUiSensor(description)
        await self._entity_platform.async_add_entities([sensor])
