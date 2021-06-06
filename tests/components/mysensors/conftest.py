"""Provide common mysensors fixtures."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import json
from typing import Any
from unittest.mock import MagicMock, patch

from mysensors.const import get_const
from mysensors.persistence import MySensorsJSONDecoder
from mysensors.sensor import Sensor
import pytest

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mysensors import CONF_VERSION, DEFAULT_BAUD_RATE
from homeassistant.components.mysensors.const import (
    CONF_BAUD_RATE,
    CONF_DEVICE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_GATEWAYS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="mqtt")
def mock_mqtt_fixture(hass) -> None:
    """Mock the MQTT integration."""
    hass.config.components.add(MQTT_DOMAIN)


@pytest.fixture(name="is_serial_port")
def is_serial_port_fixture() -> Generator[MagicMock, None, None]:
    """Patch the serial port check."""
    with patch("homeassistant.components.mysensors.gateway.cv.isdevice") as is_device:
        is_device.side_effect = lambda device: device
        yield is_device


@pytest.fixture(name="serial_gateway")
async def serial_gateway_fixture(
    is_serial_port: MagicMock,
) -> AsyncGenerator[MagicMock, None]:
    """Mock a serial gateway."""
    with patch(
        "homeassistant.components.mysensors.gateway.mysensors.AsyncSerialGateway",
        autospec=True,
    ) as gateway_class:
        gateway = gateway_class.return_value

        gateway = mock_gateway_features(gateway_class, gateway)

        yield gateway


def mock_gateway_features(gateway_class: MagicMock, gateway: MagicMock) -> MagicMock:
    """Mock the gateway features."""
    gateway.sensors = {}

    def init_gateway(*args, protocol_version="1.4", **kwargs):
        """Handle gateway creation."""
        gateway.const = get_const(protocol_version)
        gateway.metric = True
        gateway.protocol_version = protocol_version
        return gateway

    gateway_class.side_effect = init_gateway

    async def mock_start():
        """Mock the start method."""
        gateway.on_conn_made(gateway)

    gateway.start.side_effect = mock_start

    return gateway


@pytest.fixture(name="gateway")
def gateway_fixture(serial_gateway: MagicMock) -> MagicMock:
    """Return the default mocked gateway."""
    return serial_gateway


@pytest.fixture(name="serial_entry")
async def serial_entry_fixture(hass) -> MockConfigEntry:
    """Create a config entry for a serial gateway."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
            CONF_VERSION: "2.3",
            CONF_DEVICE: "/test/device",
            CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
        },
    )
    return entry


@pytest.fixture(name="config_entry")
def config_entry_fixture(serial_entry: MockConfigEntry) -> MockConfigEntry:
    """Provide the config entry used for integration set up."""
    return serial_entry


@pytest.fixture
async def integration(
    hass: HomeAssistant, gateway: MagicMock, config_entry: MockConfigEntry
) -> ConfigEntry:
    """Set up the mysensors integration with a config entry."""
    device = config_entry.data[CONF_DEVICE]
    config: dict[str, Any] = {DOMAIN: {CONF_GATEWAYS: [{CONF_DEVICE: device}]}}
    config_entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    return config_entry


def load_nodes_state(fixture_path: str) -> dict:
    """Load mysensors nodes fixture."""
    return json.loads(load_fixture(fixture_path), cls=MySensorsJSONDecoder)


@pytest.fixture(name="gps_sensor_state", scope="session")
def gps_sensor_state_fixture() -> dict:
    """Load the gps sensor state."""
    return load_nodes_state("mysensors/gps_sensor_state.json")


@pytest.fixture
def gps_sensor(gateway, gps_sensor_state) -> Sensor:
    """Load the gps sensor."""
    gateway.sensors.update(gps_sensor_state)
    node = gateway.sensors[1]
    return node
