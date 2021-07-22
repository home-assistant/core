"""Support for Dutch Smart Meter (also known as Smartmeter or P1 port)."""
from __future__ import annotations

import asyncio
from asyncio import CancelledError
from contextlib import suppress
from datetime import timedelta
from functools import partial
from typing import Any

from dsmr_parser import obis_references as obis_ref
from dsmr_parser.clients.protocol import create_dsmr_reader, create_tcp_dsmr_reader
from dsmr_parser.objects import DSMRObject
import serial
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, StateType
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
    LOGGER,
    SENSORS,
)
from .models import DSMRSensor

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Import the platform into a config entry."""
    LOGGER.warning(
        "Configuration of the DSMR platform in YAML is deprecated and will be "
        "removed in Home Assistant 2021.9; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the DSMR sensor."""
    dsmr_version = entry.data[CONF_DSMR_VERSION]
    entities = [
        DSMREntity(sensor, entry)
        for sensor in SENSORS
        if (sensor.dsmr_versions is None or dsmr_version in sensor.dsmr_versions)
        and (not sensor.is_gas or CONF_SERIAL_ID_GAS in entry.data)
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
    if CONF_HOST in entry.data:
        reader_factory = partial(
            create_tcp_dsmr_reader,
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_DSMR_VERSION],
            update_entities_telegram,
            loop=hass.loop,
            keep_alive_interval=60,
        )
    else:
        reader_factory = partial(
            create_dsmr_reader,
            entry.data[CONF_PORT],
            entry.data[CONF_DSMR_VERSION],
            update_entities_telegram,
            loop=hass.loop,
        )

    async def connect_and_reconnect() -> None:
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
                await asyncio.sleep(entry.data[CONF_RECONNECT_INTERVAL])

            except (serial.serialutil.SerialException, OSError):
                # Log any error while establishing connection and drop to retry
                # connection wait
                LOGGER.exception("Error connecting to DSMR")
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

    _attr_should_poll = False

    def __init__(self, sensor: DSMRSensor, entry: ConfigEntry) -> None:
        """Initialize entity."""
        self._sensor = sensor
        self._entry = entry
        self.telegram: dict[str, DSMRObject] = {}

        device_serial = entry.data[CONF_SERIAL_ID]
        device_name = DEVICE_NAME_ENERGY
        if sensor.is_gas:
            device_serial = entry.data[CONF_SERIAL_ID_GAS]
            device_name = DEVICE_NAME_GAS

        self._attr_device_class = sensor.device_class
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_serial)},
            "name": device_name,
        }
        self._attr_entity_registry_enabled_default = (
            sensor.entity_registry_enabled_default
        )
        self._attr_force_update = sensor.force_update
        self._attr_icon = sensor.icon
        self._attr_last_reset = sensor.last_reset
        self._attr_name = sensor.name
        self._attr_state_class = sensor.state_class
        self._attr_unique_id = f"{device_serial}_{sensor.name}".replace(" ", "_")

    @callback
    def update_data(self, telegram: dict[str, DSMRObject]) -> None:
        """Update data."""
        self.telegram = telegram
        if self.hass and self._sensor.obis_reference in self.telegram:
            self.async_write_ha_state()

    def get_dsmr_object_attr(self, attribute: str) -> str | None:
        """Read attribute from last received telegram for this DSMR object."""
        # Make sure telegram contains an object for this entities obis
        if self._sensor.obis_reference not in self.telegram:
            return None

        # Get the attribute value if the object has it
        dsmr_object = self.telegram[self._sensor.obis_reference]
        attr: str | None = getattr(dsmr_object, attribute)
        return attr

    @property
    def state(self) -> StateType:
        """Return the state of sensor, if available, translate if needed."""
        value = self.get_dsmr_object_attr("value")
        if value is None:
            return None

        if self._sensor.obis_reference == obis_ref.ELECTRICITY_ACTIVE_TARIFF:
            return self.translate_tariff(value, self._entry.data[CONF_DSMR_VERSION])

        with suppress(TypeError):
            value = round(
                float(value), self._entry.data.get(CONF_PRECISION, DEFAULT_PRECISION)
            )

        if value is not None:
            return value

        return None

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity, if any."""
        return self.get_dsmr_object_attr("unit")

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
