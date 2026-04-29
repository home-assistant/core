"""Support for reading data from a serial port."""

from __future__ import annotations

import asyncio
from asyncio import Task
import json
import logging

from serialx import Parity, SerialException, StopBits, open_serial_connection
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_XONXOFF = "xonxoff"
CONF_RTSCTS = "rtscts"
CONF_DSRDTR = "dsrdtr"

DEFAULT_NAME = "Serial Sensor"
DEFAULT_BAUDRATE = 9600
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = Parity.NONE
DEFAULT_STOPBITS = StopBits.ONE
DEFAULT_XONXOFF = False
DEFAULT_RTSCTS = False
DEFAULT_DSRDTR = False

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In([5, 6, 7, 8]),
        vol.Optional(CONF_PARITY, default=DEFAULT_PARITY): vol.In(
            [
                Parity.NONE,
                Parity.EVEN,
                Parity.ODD,
                Parity.MARK,
                Parity.SPACE,
            ]
        ),
        vol.Optional(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In(
            [
                StopBits.ONE,
                StopBits.ONE_POINT_FIVE,
                StopBits.TWO,
            ]
        ),
        vol.Optional(CONF_XONXOFF, default=DEFAULT_XONXOFF): cv.boolean,
        vol.Optional(CONF_RTSCTS, default=DEFAULT_RTSCTS): cv.boolean,
        vol.Optional(CONF_DSRDTR, default=DEFAULT_DSRDTR): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Serial sensor platform."""
    sensor = SerialSensor(
        name=config[CONF_NAME],
        port=config[CONF_SERIAL_PORT],
        baudrate=config[CONF_BAUDRATE],
        bytesize=config[CONF_BYTESIZE],
        parity=config[CONF_PARITY],
        stopbits=config[CONF_STOPBITS],
        xonxoff=config[CONF_XONXOFF],
        rtscts=config[CONF_RTSCTS],
        dsrdtr=config[CONF_DSRDTR],
        value_template=config.get(CONF_VALUE_TEMPLATE),
    )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.stop_serial_read)
    async_add_entities([sensor], True)


class SerialSensor(SensorEntity):
    """Representation of a Serial sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        port: str,
        baudrate: int,
        bytesize: int,
        parity: Parity,
        stopbits: StopBits,
        xonxoff: bool,
        rtscts: bool,
        dsrdtr: bool,
        value_template: Template | None,
    ) -> None:
        """Initialize the Serial sensor."""
        self._attr_name = name
        self._port = port
        self._baudrate = baudrate
        self._bytesize = bytesize
        self._parity = parity
        self._stopbits = stopbits
        self._xonxoff = xonxoff
        self._rtscts = rtscts
        self._dsrdtr = dsrdtr
        self._serial_loop_task: Task[None] | None = None
        self._template = value_template

    async def async_added_to_hass(self) -> None:
        """Handle when an entity is about to be added to Home Assistant."""
        self._serial_loop_task = self.hass.async_create_background_task(
            self.serial_read(
                self._port,
                self._baudrate,
                self._bytesize,
                self._parity,
                self._stopbits,
                self._xonxoff,
                self._rtscts,
                self._dsrdtr,
            ),
            "Serial reader",
        )

    async def serial_read(
        self,
        device: str,
        baudrate: int,
        bytesize: int,
        parity: Parity,
        stopbits: StopBits,
        xonxoff: bool,
        rtscts: bool,
        dsrdtr: bool,
        **kwargs,
    ):
        """Read the data from the port."""
        logged_error = False

        while True:
            reader = None
            writer = None

            try:
                reader, writer = await open_serial_connection(
                    url=device,
                    baudrate=baudrate,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                    xonxoff=xonxoff,
                    rtscts=rtscts,
                    dsrdtr=dsrdtr,
                    **kwargs,
                )
            except OSError, SerialException, TimeoutError:
                if not logged_error:
                    _LOGGER.exception(
                        "Unable to connect to the serial device %s. Will retry", device
                    )
                    logged_error = True
                await self._handle_error()
            else:
                _LOGGER.debug("Serial device %s connected", device)
                while True:
                    try:
                        line_bytes = await reader.readline()
                    except OSError, SerialException:
                        _LOGGER.exception(
                            "Error while reading serial device %s", device
                        )
                        await self._handle_error()
                        break
                    else:
                        line = line_bytes.decode("utf-8").strip()

                        try:
                            data = json.loads(line)
                        except ValueError:
                            pass
                        else:
                            if isinstance(data, dict):
                                self._attr_extra_state_attributes = data

                        if self._template is not None:
                            line = self._template.async_render_with_possible_json_value(
                                line
                            )

                        _LOGGER.debug("Received: %s", line)
                        self._attr_native_value = line
                        self.async_write_ha_state()
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()

    async def _handle_error(self):
        """Handle error for serial connection."""
        self._attr_native_value = None
        self._attr_extra_state_attributes = None
        self.async_write_ha_state()
        await asyncio.sleep(5)

    @callback
    def stop_serial_read(self, event):
        """Close resources."""
        if self._serial_loop_task:
            self._serial_loop_task.cancel()
