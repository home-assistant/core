"""Support for Dutch Smart Meter (also known as Smartmeter or P1 port)."""
from __future__ import annotations

import asyncio
from asyncio import CancelledError
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from functools import partial

from dsmr_parser import obis_references
from dsmr_parser.clients.protocol import create_dsmr_reader, create_tcp_dsmr_reader
from dsmr_parser.clients.rfxtrx_protocol import (
    create_rfxtrx_dsmr_reader,
    create_rfxtrx_tcp_dsmr_reader,
)
from dsmr_parser.objects import DSMRObject
import serial

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    VOLUME_CUBIC_METERS,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import EventType, StateType
from homeassistant.util import Throttle

from .const import (
    CONF_DSMR_VERSION,
    CONF_PRECISION,
    CONF_PROTOCOL,
    CONF_RECONNECT_INTERVAL,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    CONF_TIME_BETWEEN_UPDATE,
    DATA_TASK,
    DEFAULT_PRECISION,
    DEFAULT_RECONNECT_INTERVAL,
    DEFAULT_TIME_BETWEEN_UPDATE,
    DEVICE_NAME_ELECTRICITY,
    DEVICE_NAME_GAS,
    DOMAIN,
    DSMR_PROTOCOL,
    LOGGER,
)

UNIT_CONVERSION = {"m3": VOLUME_CUBIC_METERS}


@dataclass
class DSMRSensorEntityDescription(SensorEntityDescription):
    """Represents an DSMR Sensor."""

    dsmr_versions: set[str] | None = None
    is_gas: bool = False


SENSORS: tuple[DSMRSensorEntityDescription, ...] = (
    DSMRSensorEntityDescription(
        key=obis_references.CURRENT_ELECTRICITY_USAGE,
        name="Power Consumption",
        device_class=SensorDeviceClass.POWER,
        force_update=True,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.CURRENT_ELECTRICITY_DELIVERY,
        name="Power Production",
        device_class=SensorDeviceClass.POWER,
        force_update=True,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_ACTIVE_TARIFF,
        name="Power Tariff",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        icon="mdi:flash",
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_USED_TARIFF_1,
        name="Energy Consumption (tarif 1)",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        device_class=SensorDeviceClass.ENERGY,
        force_update=True,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_USED_TARIFF_2,
        name="Energy Consumption (tarif 2)",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_DELIVERED_TARIFF_1,
        name="Energy Production (tarif 1)",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_DELIVERED_TARIFF_2,
        name="Energy Production (tarif 2)",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE,
        name="Power Consumption Phase L1",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE,
        name="Power Consumption Phase L2",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE,
        name="Power Consumption Phase L3",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE,
        name="Power Production Phase L1",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE,
        name="Power Production Phase L2",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE,
        name="Power Production Phase L3",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.SHORT_POWER_FAILURE_COUNT,
        name="Short Power Failure Count",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        icon="mdi:flash-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.LONG_POWER_FAILURE_COUNT,
        name="Long Power Failure Count",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        icon="mdi:flash-off",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.VOLTAGE_SAG_L1_COUNT,
        name="Voltage Sags Phase L1",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.VOLTAGE_SAG_L2_COUNT,
        name="Voltage Sags Phase L2",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.VOLTAGE_SAG_L3_COUNT,
        name="Voltage Sags Phase L3",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.VOLTAGE_SWELL_L1_COUNT,
        name="Voltage Swells Phase L1",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        icon="mdi:pulse",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.VOLTAGE_SWELL_L2_COUNT,
        name="Voltage Swells Phase L2",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        icon="mdi:pulse",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.VOLTAGE_SWELL_L3_COUNT,
        name="Voltage Swells Phase L3",
        dsmr_versions={"2.2", "4", "5", "5B", "5L"},
        entity_registry_enabled_default=False,
        icon="mdi:pulse",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_VOLTAGE_L1,
        name="Voltage Phase L1",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_VOLTAGE_L2,
        name="Voltage Phase L2",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_VOLTAGE_L3,
        name="Voltage Phase L3",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_CURRENT_L1,
        name="Current Phase L1",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_CURRENT_L2,
        name="Current Phase L2",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.INSTANTANEOUS_CURRENT_L3,
        name="Current Phase L3",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.BELGIUM_MAX_POWER_PER_PHASE,
        name="Max power per phase",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.BELGIUM_MAX_CURRENT_PER_PHASE,
        name="Max current per phase",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_IMPORTED_TOTAL,
        name="Energy Consumption (total)",
        dsmr_versions={"5L", "5S", "Q3D"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.ELECTRICITY_EXPORTED_TOTAL,
        name="Energy Production (total)",
        dsmr_versions={"5L", "5S", "Q3D"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.HOURLY_GAS_METER_READING,
        name="Gas Consumption",
        dsmr_versions={"4", "5", "5L"},
        is_gas=True,
        force_update=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.BELGIUM_5MIN_GAS_METER_READING,
        name="Gas Consumption",
        dsmr_versions={"5B"},
        is_gas=True,
        force_update=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key=obis_references.GAS_METER_READING,
        name="Gas Consumption",
        dsmr_versions={"2.2"},
        is_gas=True,
        force_update=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the DSMR sensor."""
    dsmr_version = entry.data[CONF_DSMR_VERSION]
    entities = [
        DSMREntity(description, entry)
        for description in SENSORS
        if (
            description.dsmr_versions is None
            or dsmr_version in description.dsmr_versions
        )
        and (not description.is_gas or CONF_SERIAL_ID_GAS in entry.data)
    ]
    async_add_entities(entities)

    min_time_between_updates = timedelta(
        seconds=entry.options.get(CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE)
    )

    @Throttle(min_time_between_updates)
    def update_entities_telegram(telegram: dict[str, DSMRObject]) -> None:
        """Update entities with latest telegram and trigger state update."""
        # Make all device entities aware of new telegram
        for entity in entities:
            entity.update_data(telegram)

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

        while hass.state == CoreState.not_running or hass.is_running:
            # Start DSMR asyncio.Protocol reader
            try:
                transport, protocol = await hass.loop.create_task(reader_factory())

                if transport:
                    # Register listener to close transport on HA shutdown
                    @callback
                    def close_transport(_event: EventType) -> None:
                        """Close the transport on HA shutdown."""
                        if not transport:
                            return
                        transport.close()

                    stop_listener = hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STOP, close_transport
                    )

                    # Wait for reader to close
                    await protocol.wait_closed()

                    # Unexpected disconnect
                    if hass.state == CoreState.not_running or hass.is_running:
                        stop_listener()

                transport = None
                protocol = None

                # Reflect disconnect state in devices state by setting an
                # empty telegram resulting in `unknown` states
                update_entities_telegram({})

                # throttle reconnect attempts
                await asyncio.sleep(
                    entry.data.get(CONF_RECONNECT_INTERVAL, DEFAULT_RECONNECT_INTERVAL)
                )

            except (serial.serialutil.SerialException, OSError):
                # Log any error while establishing connection and drop to retry
                # connection wait
                LOGGER.exception("Error connecting to DSMR")
                transport = None
                protocol = None

                # throttle reconnect attempts
                await asyncio.sleep(
                    entry.data.get(CONF_RECONNECT_INTERVAL, DEFAULT_RECONNECT_INTERVAL)
                )
            except CancelledError:
                if stop_listener and (
                    hass.state == CoreState.not_running or hass.is_running
                ):
                    stop_listener()  # pylint: disable=not-callable

                if transport:
                    transport.close()

                if protocol:
                    await protocol.wait_closed()

                return

    # Can't be hass.async_add_job because job runs forever
    task = asyncio.create_task(connect_and_reconnect())

    # Save the task to be able to cancel it when unloading
    hass.data[DOMAIN][entry.entry_id][DATA_TASK] = task


class DSMREntity(SensorEntity):
    """Entity reading values from DSMR telegram."""

    entity_description: DSMRSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self, entity_description: DSMRSensorEntityDescription, entry: ConfigEntry
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        self._entry = entry
        self.telegram: dict[str, DSMRObject] = {}

        device_serial = entry.data[CONF_SERIAL_ID]
        device_name = DEVICE_NAME_ELECTRICITY
        if entity_description.is_gas:
            device_serial = entry.data[CONF_SERIAL_ID_GAS]
            device_name = DEVICE_NAME_GAS
        if device_serial is None:
            device_serial = entry.entry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_serial)},
            name=device_name,
        )
        self._attr_unique_id = f"{device_serial}_{entity_description.name}".replace(
            " ", "_"
        )

    @callback
    def update_data(self, telegram: dict[str, DSMRObject]) -> None:
        """Update data."""
        self.telegram = telegram
        if self.hass and self.entity_description.key in self.telegram:
            self.async_write_ha_state()

    def get_dsmr_object_attr(self, attribute: str) -> str | None:
        """Read attribute from last received telegram for this DSMR object."""
        # Make sure telegram contains an object for this entities obis
        if self.entity_description.key not in self.telegram:
            return None

        # Get the attribute value if the object has it
        dsmr_object = self.telegram[self.entity_description.key]
        attr: str | None = getattr(dsmr_object, attribute)
        return attr

    @property
    def native_value(self) -> StateType:
        """Return the state of sensor, if available, translate if needed."""
        if (value := self.get_dsmr_object_attr("value")) is None:
            return None

        if self.entity_description.key == obis_references.ELECTRICITY_ACTIVE_TARIFF:
            return self.translate_tariff(value, self._entry.data[CONF_DSMR_VERSION])

        with suppress(TypeError):
            value = round(
                float(value), self._entry.data.get(CONF_PRECISION, DEFAULT_PRECISION)
            )

        if value is not None:
            return value

        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity, if any."""
        unit_of_measurement = self.get_dsmr_object_attr("unit")
        if unit_of_measurement in UNIT_CONVERSION:
            return UNIT_CONVERSION[unit_of_measurement]
        return unit_of_measurement

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
