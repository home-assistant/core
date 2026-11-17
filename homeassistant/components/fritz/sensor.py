"""AVM FRITZ!Box binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus
from requests.exceptions import RequestException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .const import CONNECTION_TYPE_WLAN, DSL_CONNECTION, LOGGER
from .coordinator import FRITZ_DATA_KEY, AvmWrapper, FritzConfigEntry, FritzData
from .entity import (
    FritzBoxBaseCoordinatorEntity,
    FritzDeviceBase,
    FritzEntityDescription,
)
from .helpers import _is_tracked
from .models import ConnectionInfo, FritzDevice, LinkInfo

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


def _retrieve_device_uptime_state(
    status: FritzStatus, last_value: datetime | None
) -> datetime:
    """Return uptime from device."""
    return utcnow() - timedelta(seconds=status.device_uptime)


def _retrieve_connection_uptime_state(
    status: FritzStatus, last_value: datetime | None
) -> datetime:
    """Return uptime from connection."""
    return utcnow() - timedelta(seconds=status.connection_uptime)


def _retrieve_external_ip_state(status: FritzStatus, last_value: str) -> str:
    """Return external ip from device."""
    return status.external_ip  # type: ignore[no-any-return]


def _retrieve_external_ipv6_state(status: FritzStatus, last_value: str) -> str:
    """Return external ipv6 from device."""
    return str(status.external_ipv6)


def _retrieve_kb_s_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload transmission rate."""
    return round(status.transmission_rate[0] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_kb_s_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download transmission rate."""
    return round(status.transmission_rate[1] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_max_kb_s_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload max transmission rate."""
    return round(status.max_bit_rate[0] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_max_kb_s_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download max transmission rate."""
    return round(status.max_bit_rate[1] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_gb_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload total data."""
    return round(status.bytes_sent / 1000 / 1000 / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_gb_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download total data."""
    return round(status.bytes_received / 1000 / 1000 / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_link_kb_s_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload link rate."""
    return round(status.max_linked_bit_rate[0] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_link_kb_s_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download link rate."""
    return round(status.max_linked_bit_rate[1] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_link_noise_margin_sent_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return upload noise margin."""
    return status.noise_margin[0] / 10  # type: ignore[no-any-return]


def _retrieve_link_noise_margin_received_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return download noise margin."""
    return status.noise_margin[1] / 10  # type: ignore[no-any-return]


def _retrieve_link_attenuation_sent_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return upload line attenuation."""
    return status.attenuation[0] / 10  # type: ignore[no-any-return]


def _retrieve_link_attenuation_received_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return download line attenuation."""
    return status.attenuation[1] / 10  # type: ignore[no-any-return]


def _retrieve_cpu_temperature_state(
    status: FritzStatus, last_value: float | None
) -> float | None:
    """Return the first CPU temperature value."""
    try:
        return status.get_cpu_temperatures()[0]  # type: ignore[no-any-return]
    except RequestException:
        return None


def _is_suitable_cpu_temperature(status: FritzStatus) -> bool:
    """Return whether the CPU temperature sensor is suitable."""
    try:
        cpu_temp = status.get_cpu_temperatures()[0]
    except RequestException, IndexError, FritzConnectionException:
        LOGGER.debug("CPU temperature not supported by the device")
        return False
    if cpu_temp == 0:
        LOGGER.debug("CPU temperature returns 0°C, treating as not supported")
        return False
    return True


@dataclass(frozen=True, kw_only=True)
class FritzConnectionSensorEntityDescription(
    SensorEntityDescription, FritzEntityDescription
):
    """Describes Fritz connection sensor entity."""

    is_suitable: Callable[[ConnectionInfo], bool] = lambda info: info.wan_enabled


@dataclass(frozen=True, kw_only=True)
class FritzDeviceSensorEntityDescription(
    SensorEntityDescription, FritzEntityDescription
):
    """Describes Fritz device sensor entity."""

    is_suitable: Callable[[FritzStatus], bool] = lambda status: True


@dataclass(frozen=True, kw_only=True)
class FritzLinkSensorEntityDescription(SensorEntityDescription):
    """Describes Fritz connected device link sensor entity."""

    value_fn: Callable[[LinkInfo], StateType]
    is_suitable: Callable[[FritzDevice], bool] = lambda device: True
    entity_category = EntityCategory.DIAGNOSTIC
    entity_registry_enabled_default = False


CONNECTION_SENSOR_TYPES: tuple[FritzConnectionSensorEntityDescription, ...] = (
    FritzConnectionSensorEntityDescription(
        key="external_ip",
        translation_key="external_ip",
        value_fn=_retrieve_external_ip_state,
    ),
    FritzConnectionSensorEntityDescription(
        key="external_ipv6",
        translation_key="external_ipv6",
        value_fn=_retrieve_external_ipv6_state,
        is_suitable=lambda info: info.ipv6_active,
    ),
    FritzConnectionSensorEntityDescription(
        key="connection_uptime",
        translation_key="connection_uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_connection_uptime_state,
    ),
    FritzConnectionSensorEntityDescription(
        key="kb_s_sent",
        translation_key="kb_s_sent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_kb_s_sent_state,
        is_suitable=lambda info: info.addon_infos_supported,
    ),
    FritzConnectionSensorEntityDescription(
        key="kb_s_received",
        translation_key="kb_s_received",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_kb_s_received_state,
        is_suitable=lambda info: info.addon_infos_supported,
    ),
    FritzConnectionSensorEntityDescription(
        key="max_kb_s_sent",
        translation_key="max_kb_s_sent",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_max_kb_s_sent_state,
    ),
    FritzConnectionSensorEntityDescription(
        key="max_kb_s_received",
        translation_key="max_kb_s_received",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_max_kb_s_received_state,
    ),
    FritzConnectionSensorEntityDescription(
        key="gb_sent",
        translation_key="gb_sent",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=_retrieve_gb_sent_state,
        is_suitable=lambda info: info.addon_infos_supported,
    ),
    FritzConnectionSensorEntityDescription(
        key="gb_received",
        translation_key="gb_received",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=_retrieve_gb_received_state,
        is_suitable=lambda info: info.addon_infos_supported,
    ),
    FritzConnectionSensorEntityDescription(
        key="link_kb_s_sent",
        translation_key="link_kb_s_sent",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_link_kb_s_sent_state,
    ),
    FritzConnectionSensorEntityDescription(
        key="link_kb_s_received",
        translation_key="link_kb_s_received",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_link_kb_s_received_state,
    ),
    FritzConnectionSensorEntityDescription(
        key="link_noise_margin_sent",
        translation_key="link_noise_margin_sent",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_retrieve_link_noise_margin_sent_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
    FritzConnectionSensorEntityDescription(
        key="link_noise_margin_received",
        translation_key="link_noise_margin_received",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_retrieve_link_noise_margin_received_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
    FritzConnectionSensorEntityDescription(
        key="link_attenuation_sent",
        translation_key="link_attenuation_sent",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_retrieve_link_attenuation_sent_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
    FritzConnectionSensorEntityDescription(
        key="link_attenuation_received",
        translation_key="link_attenuation_received",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_retrieve_link_attenuation_received_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
)

DEVICE_SENSOR_TYPES: tuple[FritzDeviceSensorEntityDescription, ...] = (
    FritzDeviceSensorEntityDescription(
        key="device_uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_device_uptime_state,
    ),
    FritzDeviceSensorEntityDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_retrieve_cpu_temperature_state,
        is_suitable=_is_suitable_cpu_temperature,
    ),
)

LINK_SENSOR_TYPES: tuple[FritzLinkSensorEntityDescription, ...] = (
    FritzLinkSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda link_info: link_info.signal_strength,
        is_suitable=lambda device: device.connection_type == CONNECTION_TYPE_WLAN,
    ),
    FritzLinkSensorEntityDescription(
        key="link_download_rate",
        translation_key="link_download_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda link_info: link_info.download_rate,
        is_suitable=lambda device: device.connection_type == CONNECTION_TYPE_WLAN,
    ),
    FritzLinkSensorEntityDescription(
        key="link_upload_rate",
        translation_key="link_upload_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda link_info: link_info.upload_rate,
        is_suitable=lambda device: device.connection_type == CONNECTION_TYPE_WLAN,
    ),
    FritzLinkSensorEntityDescription(
        key="link_max_download_rate",
        translation_key="link_max_download_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        value_fn=lambda link_info: link_info.max_download_rate,
    ),
    FritzLinkSensorEntityDescription(
        key="link_max_upload_rate",
        translation_key="link_max_upload_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        value_fn=lambda link_info: link_info.max_upload_rate,
    ),
)


async def _async_connection_sensors(
    avm_wrapper: AvmWrapper, device_friendly_name: str
) -> list[FritzBoxSensor]:
    connection_info = await avm_wrapper.async_get_connection_info()
    return [
        FritzBoxSensor(avm_wrapper, device_friendly_name, description)
        for description in CONNECTION_SENSOR_TYPES
        if description.is_suitable(connection_info)
    ]


async def _async_device_sensors(
    avm_wrapper: AvmWrapper, device_friendly_name: str
) -> list[FritzBoxSensor]:
    def _generate_device_sensors() -> list[FritzBoxSensor]:
        return [
            FritzBoxSensor(avm_wrapper, device_friendly_name, description)
            for description in DEVICE_SENSOR_TYPES
            if description.is_suitable(avm_wrapper.fritz_status)
        ]

    return await avm_wrapper.hass.async_add_executor_job(_generate_device_sensors)


@callback
def _async_link_sensors(
    avm_wrapper: AvmWrapper,
    data_fritz: FritzData,
) -> list[FritzBoxLinkSensor]:
    """Add link sensors for connected devices once their link is known."""
    new_link_sensors: list[FritzBoxLinkSensor] = []

    known_link_sensors = data_fritz.link_sensors[avm_wrapper.unique_id]

    for mac, device in avm_wrapper.devices.items():
        if device.link_info is None:
            continue
        # Link sensor unique IDs don't include the FRITZ!Box, so only one box
        # may provide them
        if mac not in known_link_sensors and _is_tracked(
            mac, data_fritz.link_sensors.values()
        ):
            continue

        known_keys = known_link_sensors.setdefault(mac, set())
        for description in LINK_SENSOR_TYPES:
            if description.key in known_keys or not description.is_suitable(device):
                continue
            known_keys.add(description.key)
            new_link_sensors.append(
                FritzBoxLinkSensor(avm_wrapper, device, description)
            )

    return new_link_sensors


async def async_all_entities_list(
    avm_wrapper: AvmWrapper,
    device_friendly_name: str,
    data_fritz: FritzData,
) -> list[Entity]:
    """Get a list of all entities."""

    return [
        *await _async_connection_sensors(avm_wrapper, device_friendly_name),
        *await _async_device_sensors(avm_wrapper, device_friendly_name),
        *_async_link_sensors(avm_wrapper, data_fritz),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    LOGGER.debug("Setting up FRITZ!Box sensors")
    avm_wrapper = entry.runtime_data
    data_fritz = hass.data[FRITZ_DATA_KEY]

    entities_list = await async_all_entities_list(avm_wrapper, entry.title, data_fritz)
    async_add_entities(entities_list)

    @callback
    def async_update_avm_device() -> None:
        """Add link sensors that became available with the latest scan."""
        if new_link_sensors := _async_link_sensors(avm_wrapper, data_fritz):
            async_add_entities(new_link_sensors)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, avm_wrapper.signal_device_update, async_update_avm_device
        )
    )


class FritzBoxSensor(FritzBoxBaseCoordinatorEntity, SensorEntity):
    """Define FRITZ!Box connectivity class."""

    entity_description: (
        FritzConnectionSensorEntityDescription | FritzDeviceSensorEntityDescription
    )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data["entity_states"].get(self.entity_description.key)


class FritzBoxLinkSensor(FritzDeviceBase, SensorEntity):
    """Define FRITZ!Box connected device link sensor."""

    entity_description: FritzLinkSensorEntityDescription

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device: FritzDevice,
        description: FritzLinkSensorEntityDescription,
    ) -> None:
        """Initialize the link sensor."""
        super().__init__(avm_wrapper, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._mac}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        if (link_info := self._avm_wrapper.devices[self._mac].link_info) is None:
            return None
        return self.entity_description.value_fn(link_info)
