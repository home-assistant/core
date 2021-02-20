"""Support for Dutch Smart Meter (also known as Smartmeter or P1 port)."""
from __future__ import annotations

import asyncio
from asyncio import CancelledError
from contextlib import suppress
from datetime import timedelta
from functools import partial
import logging

from dsmr_parser import obis_references as obis_ref
from dsmr_parser.clients.protocol import create_dsmr_reader, create_tcp_dsmr_reader
import serial
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    TIME_HOURS,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

from .const import (
    CONF_DSMR_VERSION,
    CONF_PRECISION,
    CONF_RECONNECT_INTERVAL,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    CONF_TIME_BETWEEN_UPDATE,
    DATA_TASK,
    DEFAULT_DSMR_VERSION,
    DEFAULT_PORT,
    DEFAULT_PRECISION,
    DEFAULT_RECONNECT_INTERVAL,
    DEFAULT_TIME_BETWEEN_UPDATE,
    DEVICE_NAME_ENERGY,
    DEVICE_NAME_GAS,
    DOMAIN,
    ICON_GAS,
    ICON_POWER,
    ICON_POWER_FAILURE,
    ICON_SWELL_SAG,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
            cv.string, vol.In(["5L", "5B", "5", "4", "2.2"])
        ),
        vol.Optional(CONF_RECONNECT_INTERVAL, default=DEFAULT_RECONNECT_INTERVAL): int,
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.Coerce(int),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the platform into a config entry."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the DSMR sensor."""
    config = entry.data
    options = entry.options

    dsmr_version = config[CONF_DSMR_VERSION]

    # Define list of name,obis,force_update mappings to generate entities
    obis_mapping = [
        ["Power Consumption", obis_ref.CURRENT_ELECTRICITY_USAGE, True],
        ["Power Production", obis_ref.CURRENT_ELECTRICITY_DELIVERY, True],
        ["Energy Tariff", obis_ref.ELECTRICITY_ACTIVE_TARIFF, False],
        ["Energy Consumption (tarif 1)", obis_ref.ELECTRICITY_USED_TARIFF_1, True],
        ["Energy Consumption (tarif 2)", obis_ref.ELECTRICITY_USED_TARIFF_2, True],
        ["Energy Production (tarif 1)", obis_ref.ELECTRICITY_DELIVERED_TARIFF_1, True],
        ["Energy Production (tarif 2)", obis_ref.ELECTRICITY_DELIVERED_TARIFF_2, True],
        [
            "Power Consumption Phase L1",
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE,
            False,
        ],
        [
            "Power Consumption Phase L2",
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE,
            False,
        ],
        [
            "Power Consumption Phase L3",
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE,
            False,
        ],
        [
            "Power Production Phase L1",
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE,
            False,
        ],
        [
            "Power Production Phase L2",
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE,
            False,
        ],
        [
            "Power Production Phase L3",
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE,
            False,
        ],
        ["Short Power Failure Count", obis_ref.SHORT_POWER_FAILURE_COUNT, False],
        ["Long Power Failure Count", obis_ref.LONG_POWER_FAILURE_COUNT, False],
        ["Voltage Sags Phase L1", obis_ref.VOLTAGE_SAG_L1_COUNT, False],
        ["Voltage Sags Phase L2", obis_ref.VOLTAGE_SAG_L2_COUNT, False],
        ["Voltage Sags Phase L3", obis_ref.VOLTAGE_SAG_L3_COUNT, False],
        ["Voltage Swells Phase L1", obis_ref.VOLTAGE_SWELL_L1_COUNT, False],
        ["Voltage Swells Phase L2", obis_ref.VOLTAGE_SWELL_L2_COUNT, False],
        ["Voltage Swells Phase L3", obis_ref.VOLTAGE_SWELL_L3_COUNT, False],
        ["Voltage Phase L1", obis_ref.INSTANTANEOUS_VOLTAGE_L1, False],
        ["Voltage Phase L2", obis_ref.INSTANTANEOUS_VOLTAGE_L2, False],
        ["Voltage Phase L3", obis_ref.INSTANTANEOUS_VOLTAGE_L3, False],
        ["Current Phase L1", obis_ref.INSTANTANEOUS_CURRENT_L1, False],
        ["Current Phase L2", obis_ref.INSTANTANEOUS_CURRENT_L2, False],
        ["Current Phase L3", obis_ref.INSTANTANEOUS_CURRENT_L3, False],
    ]

    if dsmr_version == "5L":
        obis_mapping.extend(
            [
                [
                    "Energy Consumption (total)",
                    obis_ref.LUXEMBOURG_ELECTRICITY_USED_TARIFF_GLOBAL,
                    True,
                ],
                [
                    "Energy Production (total)",
                    obis_ref.LUXEMBOURG_ELECTRICITY_DELIVERED_TARIFF_GLOBAL,
                    True,
                ],
            ]
        )
    else:
        obis_mapping.extend(
            [["Energy Consumption (total)", obis_ref.ELECTRICITY_IMPORTED_TOTAL, True]]
        )

    # Generate device entities
    devices = [
        DSMREntity(
            name, DEVICE_NAME_ENERGY, config[CONF_SERIAL_ID], obis, config, force_update
        )
        for name, obis, force_update in obis_mapping
    ]

    # Protocol version specific obis
    if CONF_SERIAL_ID_GAS in config:
        if dsmr_version in ("4", "5", "5L"):
            gas_obis = obis_ref.HOURLY_GAS_METER_READING
        elif dsmr_version in ("5B",):
            gas_obis = obis_ref.BELGIUM_HOURLY_GAS_METER_READING
        else:
            gas_obis = obis_ref.GAS_METER_READING

        # Add gas meter reading and derivative for usage
        devices += [
            DSMREntity(
                "Gas Consumption",
                DEVICE_NAME_GAS,
                config[CONF_SERIAL_ID_GAS],
                gas_obis,
                config,
                True,
            ),
            DerivativeDSMREntity(
                "Hourly Gas Consumption",
                DEVICE_NAME_GAS,
                config[CONF_SERIAL_ID_GAS],
                gas_obis,
                config,
                False,
            ),
        ]

    async_add_entities(devices)

    min_time_between_updates = timedelta(
        seconds=options.get(CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE)
    )

    @Throttle(min_time_between_updates)
    def update_entities_telegram(telegram):
        """Update entities with latest telegram and trigger state update."""
        # Make all device entities aware of new telegram
        for device in devices:
            device.update_data(telegram)

    # Creates an asyncio.Protocol factory for reading DSMR telegrams from
    # serial and calls update_entities_telegram to update entities on arrival
    if CONF_HOST in config:
        reader_factory = partial(
            create_tcp_dsmr_reader,
            config[CONF_HOST],
            config[CONF_PORT],
            config[CONF_DSMR_VERSION],
            update_entities_telegram,
            loop=hass.loop,
            keep_alive_interval=60,
        )
    else:
        reader_factory = partial(
            create_dsmr_reader,
            config[CONF_PORT],
            config[CONF_DSMR_VERSION],
            update_entities_telegram,
            loop=hass.loop,
        )

    async def connect_and_reconnect():
        """Connect to DSMR and keep reconnecting until Home Assistant stops."""
        stop_listener = None
        transport = None
        protocol = None

        while hass.state != CoreState.stopping:
            # Start DSMR asyncio.Protocol reader
            try:
                transport, protocol = await hass.loop.create_task(reader_factory())

                if transport:
                    # Register listener to close transport on HA shutdown
                    stop_listener = hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STOP, transport.close
                    )

                    # Wait for reader to close
                    await protocol.wait_closed()

                    # Unexpected disconnect
                    if not hass.is_stopping:
                        stop_listener()

                transport = None
                protocol = None

                # Reflect disconnect state in devices state by setting an
                # empty telegram resulting in `unknown` states
                update_entities_telegram({})

                # throttle reconnect attempts
                await asyncio.sleep(config[CONF_RECONNECT_INTERVAL])

            except (serial.serialutil.SerialException, OSError):
                # Log any error while establishing connection and drop to retry
                # connection wait
                _LOGGER.exception("Error connecting to DSMR")
                transport = None
                protocol = None
            except CancelledError:
                if stop_listener:
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

    def __init__(self, name, device_name, device_serial, obis, config, force_update):
        """Initialize entity."""
        self._name = name
        self._obis = obis
        self._config = config
        self.telegram = {}

        self._device_name = device_name
        self._device_serial = device_serial
        self._force_update = force_update
        self._unique_id = f"{device_serial}_{name}".replace(" ", "_")

    @callback
    def update_data(self, telegram):
        """Update data."""
        self.telegram = telegram
        if self.hass and self._obis in self.telegram:
            self.async_write_ha_state()

    def get_dsmr_object_attr(self, attribute):
        """Read attribute from last received telegram for this DSMR object."""
        # Make sure telegram contains an object for this entities obis
        if self._obis not in self.telegram:
            return None

        # Get the attribute value if the object has it
        dsmr_object = self.telegram[self._obis]
        return getattr(dsmr_object, attribute, None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if "Sags" in self._name or "Swells" in self.name:
            return ICON_SWELL_SAG
        if "Failure" in self._name:
            return ICON_POWER_FAILURE
        if "Power" in self._name:
            return ICON_POWER
        if "Gas" in self._name:
            return ICON_GAS

    @property
    def state(self):
        """Return the state of sensor, if available, translate if needed."""
        value = self.get_dsmr_object_attr("value")

        if self._obis == obis_ref.ELECTRICITY_ACTIVE_TARIFF:
            return self.translate_tariff(value, self._config[CONF_DSMR_VERSION])

        with suppress(TypeError):
            value = round(float(value), self._config[CONF_PRECISION])

        if value is not None:
            return value

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.get_dsmr_object_attr("unit")

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._device_serial)},
            "name": self._device_name,
        }

    @property
    def force_update(self):
        """Force update."""
        return self._force_update

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @staticmethod
    def translate_tariff(value, dsmr_version):
        """Convert 2/1 to normal/low depending on DSMR version."""
        # DSMR V5B: Note: In Belgium values are swapped:
        # Rate code 2 is used for low rate and rate code 1 is used for normal rate.
        if dsmr_version in ("5B",):
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


class DerivativeDSMREntity(DSMREntity):
    """Calculated derivative for values where the DSMR doesn't offer one.

    Gas readings are only reported per hour and don't offer a rate only
    the current meter reading. This entity converts subsequents readings
    into a hourly rate.
    """

    _previous_reading = None
    _previous_timestamp = None
    _state = None

    @property
    def state(self):
        """Return the calculated current hourly rate."""
        return self._state

    @property
    def force_update(self):
        """Disable force update."""
        return False

    @property
    def should_poll(self):
        """Enable polling."""
        return True

    async def async_update(self):
        """Recalculate hourly rate if timestamp has changed.

        DSMR updates gas meter reading every hour. Along with the new
        value a timestamp is provided for the reading. Test if the last
        known timestamp differs from the current one then calculate a
        new rate for the previous hour.

        """
        # check if the timestamp for the object differs from the previous one
        timestamp = self.get_dsmr_object_attr("datetime")
        if timestamp and timestamp != self._previous_timestamp:
            current_reading = self.get_dsmr_object_attr("value")

            if self._previous_reading is None:
                # Can't calculate rate without previous datapoint
                # just store current point
                pass
            else:
                # Recalculate the rate
                diff = current_reading - self._previous_reading
                timediff = timestamp - self._previous_timestamp
                total_seconds = timediff.total_seconds()
                self._state = round(float(diff) / total_seconds * 3600, 3)

            self._previous_reading = current_reading
            self._previous_timestamp = timestamp

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, per hour, if any."""
        unit = self.get_dsmr_object_attr("unit")
        if unit:
            return f"{unit}/{TIME_HOURS}"
