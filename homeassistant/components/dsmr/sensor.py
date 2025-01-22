"""Support for Dutch Smart Meter (also known as Smartmeter or P1 port)."""

from __future__ import annotations

import asyncio
from asyncio import CancelledError
from collections.abc import Callable, Generator
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from functools import partial

from dsmr_parser.clients.protocol import create_dsmr_reader, create_tcp_dsmr_reader
from dsmr_parser.clients.rfxtrx_protocol import (
    create_rfxtrx_dsmr_reader,
    create_rfxtrx_tcp_dsmr_reader,
)
from dsmr_parser.objects import DSMRObject, MbusDevice, Telegram
import serial

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
    EntityCategory,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import Throttle

from . import DsmrConfigEntry
from .const import (
    CONF_DSMR_VERSION,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    CONF_TIME_BETWEEN_UPDATE,
    DEFAULT_PRECISION,
    DEFAULT_RECONNECT_INTERVAL,
    DEFAULT_TIME_BETWEEN_UPDATE,
    DEVICE_NAME_ELECTRICITY,
    DEVICE_NAME_GAS,
    DEVICE_NAME_HEAT,
    DEVICE_NAME_WATER,
    DOMAIN,
    DSMR_PROTOCOL,
    LOGGER,
)

EVENT_FIRST_TELEGRAM = "dsmr_first_telegram_{}"

UNIT_CONVERSION = {"m3": UnitOfVolume.CUBIC_METERS}


@dataclass(frozen=True, kw_only=True)
class DSMRSensorEntityDescription(SensorEntityDescription):
    """Represents an DSMR Sensor."""

    dsmr_versions: set[str] | None = None
    is_gas: bool = False
    is_water: bool = False
    is_heat: bool = False
    obis_reference: str


class MbusDeviceType(IntEnum):
    """Types of mbus devices (13757-3:2013)."""

    GAS = 3
    HEAT = 4
    WATER = 7


SENSORS: tuple[DSMRSensorEntityDescription, ...] = (
    DSMRSensorEntityDescription(
        key="timestamp",
        obis_reference="P1_MESSAGE_TIMESTAMP",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    DSMRSensorEntityDescription(
        key="current_electricity_usage",
        translation_key="current_electricity_usage",
        obis_reference="CURRENT_ELECTRICITY_USAGE",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="current_electricity_delivery",
        translation_key="current_electricity_delivery",
        obis_reference="CURRENT_ELECTRICITY_DELIVERY",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="electricity_active_tariff",
        translation_key="electricity_active_tariff",
        obis_reference="ELECTRICITY_ACTIVE_TARIFF",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        device_class=SensorDeviceClass.ENUM,
        options=["low", "normal"],
    ),
    DSMRSensorEntityDescription(
        key="electricity_used_tariff_1",
        translation_key="electricity_used_tariff_1",
        obis_reference="ELECTRICITY_USED_TARIFF_1",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_used_tariff_2",
        translation_key="electricity_used_tariff_2",
        obis_reference="ELECTRICITY_USED_TARIFF_2",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_delivered_tariff_1",
        translation_key="electricity_delivered_tariff_1",
        obis_reference="ELECTRICITY_DELIVERED_TARIFF_1",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_delivered_tariff_2",
        translation_key="electricity_delivered_tariff_2",
        obis_reference="ELECTRICITY_DELIVERED_TARIFF_2",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l1_positive",
        translation_key="instantaneous_active_power_l1_positive",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l2_positive",
        translation_key="instantaneous_active_power_l2_positive",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l3_positive",
        translation_key="instantaneous_active_power_l3_positive",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l1_negative",
        translation_key="instantaneous_active_power_l1_negative",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l2_negative",
        translation_key="instantaneous_active_power_l2_negative",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l3_negative",
        translation_key="instantaneous_active_power_l3_negative",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="short_power_failure_count",
        translation_key="short_power_failure_count",
        obis_reference="SHORT_POWER_FAILURE_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="long_power_failure_count",
        translation_key="long_power_failure_count",
        obis_reference="LONG_POWER_FAILURE_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_sag_l1_count",
        translation_key="voltage_sag_l1_count",
        obis_reference="VOLTAGE_SAG_L1_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_sag_l2_count",
        translation_key="voltage_sag_l2_count",
        obis_reference="VOLTAGE_SAG_L2_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_sag_l3_count",
        translation_key="voltage_sag_l3_count",
        obis_reference="VOLTAGE_SAG_L3_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_swell_l1_count",
        translation_key="voltage_swell_l1_count",
        obis_reference="VOLTAGE_SWELL_L1_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_swell_l2_count",
        translation_key="voltage_swell_l2_count",
        obis_reference="VOLTAGE_SWELL_L2_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_swell_l3_count",
        translation_key="voltage_swell_l3_count",
        obis_reference="VOLTAGE_SWELL_L3_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_voltage_l1",
        translation_key="instantaneous_voltage_l1",
        obis_reference="INSTANTANEOUS_VOLTAGE_L1",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_voltage_l2",
        translation_key="instantaneous_voltage_l2",
        obis_reference="INSTANTANEOUS_VOLTAGE_L2",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_voltage_l3",
        translation_key="instantaneous_voltage_l3",
        obis_reference="INSTANTANEOUS_VOLTAGE_L3",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_current_l1",
        translation_key="instantaneous_current_l1",
        obis_reference="INSTANTANEOUS_CURRENT_L1",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_current_l2",
        translation_key="instantaneous_current_l2",
        obis_reference="INSTANTANEOUS_CURRENT_L2",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_current_l3",
        translation_key="instantaneous_current_l3",
        obis_reference="INSTANTANEOUS_CURRENT_L3",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="belgium_max_power_per_phase",
        translation_key="max_power_per_phase",
        obis_reference="ACTUAL_TRESHOLD_ELECTRICITY",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="belgium_max_current_per_phase",
        translation_key="max_current_per_phase",
        obis_reference="FUSE_THRESHOLD_L1",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="electricity_imported_total",
        translation_key="electricity_imported_total",
        obis_reference="ELECTRICITY_IMPORTED_TOTAL",
        dsmr_versions={"5L", "5S", "Q3D"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_exported_total",
        translation_key="electricity_exported_total",
        obis_reference="ELECTRICITY_EXPORTED_TOTAL",
        dsmr_versions={"5L", "5S", "Q3D"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="belgium_current_average_demand",
        translation_key="current_average_demand",
        obis_reference="BELGIUM_CURRENT_AVERAGE_DEMAND",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="belgium_maximum_demand_current_month",
        translation_key="maximum_demand_current_month",
        obis_reference="BELGIUM_MAXIMUM_DEMAND_MONTH",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="hourly_gas_meter_reading",
        translation_key="gas_meter_reading",
        obis_reference="HOURLY_GAS_METER_READING",
        dsmr_versions={"4", "5", "5L"},
        is_gas=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="gas_meter_reading",
        translation_key="gas_meter_reading",
        obis_reference="GAS_METER_READING",
        dsmr_versions={"2.2"},
        is_gas=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

SENSORS_MBUS_DEVICE_TYPE: dict[int, tuple[DSMRSensorEntityDescription, ...]] = {
    MbusDeviceType.GAS: (
        DSMRSensorEntityDescription(
            key="gas_reading",
            translation_key="gas_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_gas=True,
            device_class=SensorDeviceClass.GAS,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    MbusDeviceType.HEAT: (
        DSMRSensorEntityDescription(
            key="heat_reading",
            translation_key="heat_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_heat=True,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    MbusDeviceType.WATER: (
        DSMRSensorEntityDescription(
            key="water_reading",
            translation_key="water_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_water=True,
            device_class=SensorDeviceClass.WATER,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
}


def device_class_and_uom(
    data: Telegram | MbusDevice,
    entity_description: DSMRSensorEntityDescription,
) -> tuple[SensorDeviceClass | None, str | None]:
    """Get native unit of measurement from telegram,."""
    dsmr_object = getattr(data, entity_description.obis_reference)
    uom: str | None = getattr(dsmr_object, "unit") or None
    with suppress(ValueError):
        if entity_description.device_class == SensorDeviceClass.GAS and (
            enery_uom := UnitOfEnergy(str(uom))
        ):
            return (SensorDeviceClass.ENERGY, enery_uom)
    if uom in UNIT_CONVERSION:
        return (entity_description.device_class, UNIT_CONVERSION[uom])
    return (entity_description.device_class, uom)


def rename_old_gas_to_mbus(
    hass: HomeAssistant, entry: ConfigEntry, mbus_device_id: str
) -> None:
    """Rename old gas sensor to mbus variant."""
    dev_reg = dr.async_get(hass)
    for dev_id in (mbus_device_id, entry.entry_id):
        device_entry_v1 = dev_reg.async_get_device(identifiers={(DOMAIN, dev_id)})
        if device_entry_v1 is not None:
            device_id = device_entry_v1.id

            ent_reg = er.async_get(hass)
            entries = er.async_entries_for_device(ent_reg, device_id)

            for entity in entries:
                if entity.unique_id.endswith(
                    "belgium_5min_gas_meter_reading"
                ) or entity.unique_id.endswith("hourly_gas_meter_reading"):
                    if ent_reg.async_get_entity_id(
                        SENSOR_DOMAIN, DOMAIN, mbus_device_id
                    ):
                        LOGGER.debug(
                            "Skip migration of %s because it already exists",
                            entity.entity_id,
                        )
                        continue
                    new_device = dev_reg.async_get_or_create(
                        config_entry_id=entry.entry_id,
                        identifiers={(DOMAIN, mbus_device_id)},
                    )
                    ent_reg.async_update_entity(
                        entity.entity_id,
                        new_unique_id=mbus_device_id,
                        device_id=new_device.id,
                    )
                    LOGGER.debug(
                        "Migrated entity %s from unique id %s to %s",
                        entity.entity_id,
                        entity.unique_id,
                        mbus_device_id,
                    )
            # Cleanup old device
            dev_entities = er.async_entries_for_device(
                ent_reg, device_id, include_disabled_entities=True
            )
            if not dev_entities:
                dev_reg.async_remove_device(device_id)


def is_supported_description(
    data: Telegram | MbusDevice,
    description: DSMRSensorEntityDescription,
    dsmr_version: str,
) -> bool:
    """Check if this is a supported description for this telegram."""
    return hasattr(data, description.obis_reference) and (
        description.dsmr_versions is None or dsmr_version in description.dsmr_versions
    )


def create_mbus_entities(
    hass: HomeAssistant, telegram: Telegram, entry: ConfigEntry, dsmr_version: str
) -> Generator[DSMREntity]:
    """Create MBUS Entities."""
    mbus_devices: list[MbusDevice] = getattr(telegram, "MBUS_DEVICES", [])
    for device in mbus_devices:
        if (device_type := getattr(device, "MBUS_DEVICE_TYPE", None)) is None:
            continue
        type_ = int(device_type.value)

        if type_ not in SENSORS_MBUS_DEVICE_TYPE:
            LOGGER.warning("Unsupported MBUS_DEVICE_TYPE (%d)", type_)
            continue

        if identifier := getattr(device, "MBUS_EQUIPMENT_IDENTIFIER", None):
            serial_ = identifier.value
            rename_old_gas_to_mbus(hass, entry, serial_)
        else:
            serial_ = ""

        for description in SENSORS_MBUS_DEVICE_TYPE.get(type_, ()):
            if not is_supported_description(device, description, dsmr_version):
                continue
            yield DSMREntity(
                description,
                entry,
                telegram,
                *device_class_and_uom(device, description),  # type: ignore[arg-type]
                serial_,
                device.channel_id,
            )


def get_dsmr_object(
    telegram: Telegram | None, mbus_id: int, obis_reference: str
) -> DSMRObject | None:
    """Extract DSMR object from telegram."""
    if not telegram:
        return None

    telegram_or_device: Telegram | MbusDevice | None = telegram
    if mbus_id:
        telegram_or_device = telegram.get_mbus_device_by_channel(mbus_id)
        if telegram_or_device is None:
            return None

    return getattr(telegram_or_device, obis_reference, None)


async def async_setup_entry(
    hass: HomeAssistant, entry: DsmrConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the DSMR sensor."""
    dsmr_version = entry.data[CONF_DSMR_VERSION]
    entities: list[DSMREntity] = []
    initialized: bool = False
    add_entities_handler: Callable[[], None] | None

    @callback
    def init_async_add_entities(telegram: Telegram) -> None:
        """Add the sensor entities after the first telegram was received."""
        nonlocal add_entities_handler
        assert add_entities_handler is not None
        add_entities_handler()
        add_entities_handler = None

        entities.extend(create_mbus_entities(hass, telegram, entry, dsmr_version))

        entities.extend(
            [
                DSMREntity(
                    description,
                    entry,
                    telegram,
                    *device_class_and_uom(telegram, description),  # type: ignore[arg-type]
                )
                for description in SENSORS
                if is_supported_description(telegram, description, dsmr_version)
                and (
                    (not description.is_gas and not description.is_heat)
                    or CONF_SERIAL_ID_GAS in entry.data
                )
            ]
        )
        async_add_entities(entities)

    add_entities_handler = async_dispatcher_connect(
        hass, EVENT_FIRST_TELEGRAM.format(entry.entry_id), init_async_add_entities
    )
    min_time_between_updates = timedelta(
        seconds=entry.options.get(CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE)
    )

    @Throttle(min_time_between_updates)
    def update_entities_telegram(telegram: Telegram | None) -> None:
        """Update entities with latest telegram and trigger state update."""
        nonlocal initialized
        # Make all device entities aware of new telegram
        for entity in entities:
            entity.update_data(telegram)

        entry.runtime_data.telegram = telegram

        if not initialized and telegram:
            initialized = True
            async_dispatcher_send(
                hass, EVENT_FIRST_TELEGRAM.format(entry.entry_id), telegram
            )

    # Creates an asyncio.Protocol factory for reading DSMR telegrams from
    # serial and calls update_entities_telegram to update entities on arrival
    protocol = entry.data.get(CONF_PROTOCOL, DSMR_PROTOCOL)
    if CONF_HOST in entry.data:
        if protocol == DSMR_PROTOCOL:
            create_reader = create_tcp_dsmr_reader
        else:
            create_reader = create_rfxtrx_tcp_dsmr_reader
        reader_factory = partial(
            create_reader,
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            dsmr_version,
            update_entities_telegram,
            loop=hass.loop,
            keep_alive_interval=60,
        )
    else:
        if protocol == DSMR_PROTOCOL:
            create_reader = create_dsmr_reader
        else:
            create_reader = create_rfxtrx_dsmr_reader
        reader_factory = partial(
            create_reader,
            entry.data[CONF_PORT],
            dsmr_version,
            update_entities_telegram,
            loop=hass.loop,
        )

    async def connect_and_reconnect() -> None:
        """Connect to DSMR and keep reconnecting until Home Assistant stops."""
        stop_listener = None
        transport = None
        protocol = None

        while hass.state is CoreState.not_running or hass.is_running:
            # Start DSMR asyncio.Protocol reader

            # Reflect connected state in devices state by setting an
            # empty telegram resulting in `unknown` states
            update_entities_telegram({})

            try:
                transport, protocol = await hass.loop.create_task(reader_factory())

                if transport:
                    # Register listener to close transport on HA shutdown
                    @callback
                    def close_transport(_event: Event) -> None:
                        """Close the transport on HA shutdown."""
                        if not transport:  # noqa: B023
                            return
                        transport.close()  # noqa: B023

                    stop_listener = hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STOP, close_transport
                    )

                    # Wait for reader to close
                    await protocol.wait_closed()

                    # Unexpected disconnect
                    if hass.state is CoreState.not_running or hass.is_running:
                        stop_listener()

                transport = None
                protocol = None

                # Reflect disconnect state in devices state by setting an
                # None telegram resulting in `unavailable` states
                update_entities_telegram(None)

                # throttle reconnect attempts
                await asyncio.sleep(DEFAULT_RECONNECT_INTERVAL)

            except (serial.SerialException, OSError):
                # Log any error while establishing connection and drop to retry
                # connection wait
                LOGGER.exception("Error connecting to DSMR")
                transport = None
                protocol = None

                # Reflect disconnect state in devices state by setting an
                # None telegram resulting in `unavailable` states
                update_entities_telegram(None)

                # throttle reconnect attempts
                await asyncio.sleep(DEFAULT_RECONNECT_INTERVAL)
            except CancelledError:
                # Reflect disconnect state in devices state by setting an
                # None telegram resulting in `unavailable` states
                update_entities_telegram(None)

                if stop_listener and (
                    hass.state is CoreState.not_running or hass.is_running
                ):
                    stop_listener()

                if transport:
                    transport.close()

                if protocol:
                    await protocol.wait_closed()

                return

    # Can't be hass.async_add_job because job runs forever
    task = asyncio.create_task(connect_and_reconnect())

    @callback
    def _async_stop(_: Event) -> None:
        if add_entities_handler is not None:
            add_entities_handler()
        task.cancel()

    # Make sure task is cancelled on shutdown (or tests complete)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    # Save the task to be able to cancel it when unloading
    entry.runtime_data.task = task


class DSMREntity(SensorEntity):
    """Entity reading values from DSMR telegram."""

    entity_description: DSMRSensorEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entity_description: DSMRSensorEntityDescription,
        entry: ConfigEntry,
        telegram: Telegram,
        device_class: SensorDeviceClass,
        native_unit_of_measurement: str | None,
        serial_id: str = "",
        mbus_id: int = 0,
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._entry = entry
        self.telegram: Telegram | None = telegram

        device_serial = entry.data[CONF_SERIAL_ID]
        device_name = DEVICE_NAME_ELECTRICITY
        if entity_description.is_gas:
            if serial_id:
                device_serial = serial_id
            else:
                device_serial = entry.data[CONF_SERIAL_ID_GAS]
            device_name = DEVICE_NAME_GAS
        if entity_description.is_water:
            if serial_id:
                device_serial = serial_id
            device_name = DEVICE_NAME_WATER
        if entity_description.is_heat:
            if serial_id:
                device_serial = serial_id
            device_name = DEVICE_NAME_HEAT
        if device_serial is None:
            device_serial = entry.entry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_serial)},
            name=device_name,
        )
        self._mbus_id = mbus_id
        if mbus_id != 0:
            if serial_id:
                self._attr_unique_id = f"{device_serial}"
            else:
                self._attr_unique_id = f"{device_serial}_{mbus_id}"
        else:
            self._attr_unique_id = f"{device_serial}_{entity_description.key}"

    @callback
    def update_data(self, telegram: Telegram | None) -> None:
        """Update data."""
        self.telegram = telegram
        if self.hass and (
            telegram is None
            or get_dsmr_object(
                telegram, self._mbus_id, self.entity_description.obis_reference
            )
        ):
            self.async_write_ha_state()

    def get_dsmr_object_attr(self, attribute: str) -> str | None:
        """Read attribute from last received telegram for this DSMR object."""
        # Get the object
        dsmr_object = get_dsmr_object(
            self.telegram, self._mbus_id, self.entity_description.obis_reference
        )
        if dsmr_object is None:
            return None

        # Get the attribute value if the object has it
        attr: str | None = getattr(dsmr_object, attribute)
        return attr

    @property
    def available(self) -> bool:
        """Entity is only available if there is a telegram."""
        return self.telegram is not None

    @property
    def native_value(self) -> StateType:
        """Return the state of sensor, if available, translate if needed."""
        value: StateType
        if (value := self.get_dsmr_object_attr("value")) is None:
            return None

        if self.entity_description.obis_reference == "ELECTRICITY_ACTIVE_TARIFF":
            return self.translate_tariff(value, self._entry.data[CONF_DSMR_VERSION])

        with suppress(TypeError):
            value = round(float(value), DEFAULT_PRECISION)

        # Make sure we do not return a zero value for an energy sensor
        if not value and self.state_class == SensorStateClass.TOTAL_INCREASING:
            return None

        return value

    @staticmethod
    def translate_tariff(value: str, dsmr_version: str) -> str | None:
        """Convert 2/1 to normal/low depending on DSMR version."""
        # DSMR V5B: Note: In Belgium values are swapped:
        # Rate code 2 is used for low rate and rate code 1 is used for normal rate.
        if dsmr_version == "5B":
            if value == "0001":
                value = "0002"
            elif value == "0002":
                value = "0001"
        # DSMR V2.2: Note: Rate code 1 is used for low rate and rate code 2 is
        # used for normal rate.
        if value == "0002":
            return "normal"
        if value == "0001":
            return "low"

        return None
