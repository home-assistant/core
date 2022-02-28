"""Provide common mysensors fixtures."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Generator
import json
from typing import Any
from unittest.mock import MagicMock, patch

from mysensors import BaseSyncGateway
from mysensors.persistence import MySensorsJSONDecoder
from mysensors.sensor import Sensor
import pytest

from homeassistant.components.device_tracker.legacy import Device
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
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(autouse=True)
def device_tracker_storage(mock_device_tracker_conf: list[Device]) -> list[Device]:
    """Mock out device tracker known devices storage."""
    devices = mock_device_tracker_conf
    return devices


@pytest.fixture(name="mqtt")
def mock_mqtt_fixture(hass: HomeAssistant) -> None:
    """Mock the MQTT integration."""
    hass.config.components.add(MQTT_DOMAIN)


@pytest.fixture(name="is_serial_port")
def is_serial_port_fixture() -> Generator[MagicMock, None, None]:
    """Patch the serial port check."""
    with patch("homeassistant.components.mysensors.gateway.cv.isdevice") as is_device:
        is_device.side_effect = lambda device: device
        yield is_device


@pytest.fixture(name="gateway_nodes")
def gateway_nodes_fixture() -> dict[int, Sensor]:
    """Return the gateway nodes dict."""
    return {}


@pytest.fixture(name="serial_transport")
async def serial_transport_fixture(
    gateway_nodes: dict[int, Sensor],
    is_serial_port: MagicMock,
) -> AsyncGenerator[dict[int, Sensor], None]:
    """Mock a serial transport."""
    with patch(
        "mysensors.gateway_serial.AsyncTransport", autospec=True
    ) as transport_class, patch("mysensors.AsyncTasks", autospec=True) as tasks_class:
        tasks = tasks_class.return_value
        tasks.persistence = MagicMock

        mock_gateway_features(tasks, transport_class, gateway_nodes)

        yield transport_class


def mock_gateway_features(
    tasks: MagicMock, transport_class: MagicMock, nodes: dict[int, Sensor]
) -> None:
    """Mock the gateway features."""

    async def mock_start_persistence() -> None:
        """Load nodes from via persistence."""
        gateway = transport_class.call_args[0][0]
        gateway.sensors.update(nodes)

    tasks.start_persistence.side_effect = mock_start_persistence

    async def mock_start() -> None:
        """Mock the start method."""
        gateway = transport_class.call_args[0][0]
        gateway.on_conn_made(gateway)

    tasks.start.side_effect = mock_start


@pytest.fixture(name="transport")
def transport_fixture(serial_transport: MagicMock) -> MagicMock:
    """Return the default mocked transport."""
    return serial_transport


@pytest.fixture(name="serial_entry")
async def serial_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
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
    hass: HomeAssistant, transport: MagicMock, config_entry: MockConfigEntry
) -> AsyncGenerator[tuple[MockConfigEntry, Callable[[str], None]], None]:
    """Set up the mysensors integration with a config entry."""
    device = config_entry.data[CONF_DEVICE]
    config: dict[str, Any] = {DOMAIN: {CONF_GATEWAYS: [{CONF_DEVICE: device}]}}
    config_entry.add_to_hass(hass)

    def receive_message(message_string: str) -> None:
        """Receive a message with the transport.

        The message_string parameter is a string in the MySensors message format.
        """
        gateway = transport.call_args[0][0]
        # node_id;child_id;command;ack;type;payload\n
        gateway.logic(message_string)

    with patch("homeassistant.components.mysensors.device.UPDATE_DELAY", new=0):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield config_entry, receive_message


@pytest.fixture(name="gateway")
def gateway_fixture(transport, integration) -> BaseSyncGateway:
    """Return a setup gateway."""
    return transport.call_args[0][0]


def load_nodes_state(fixture_path: str) -> dict:
    """Load mysensors nodes fixture."""
    return json.loads(load_fixture(fixture_path), cls=MySensorsJSONDecoder)


def update_gateway_nodes(
    gateway_nodes: dict[int, Sensor], nodes: dict[int, Sensor]
) -> dict:
    """Update the gateway nodes."""
    gateway_nodes.update(nodes)
    return nodes


@pytest.fixture(name="gps_sensor_state", scope="session")
def gps_sensor_state_fixture() -> dict:
    """Load the gps sensor state."""
    return load_nodes_state("mysensors/gps_sensor_state.json")


@pytest.fixture
def gps_sensor(gateway_nodes: dict[int, Sensor], gps_sensor_state: dict) -> Sensor:
    """Load the gps sensor."""
    nodes = update_gateway_nodes(gateway_nodes, gps_sensor_state)
    node = nodes[1]
    return node


@pytest.fixture(name="power_sensor_state", scope="session")
def power_sensor_state_fixture() -> dict:
    """Load the power sensor state."""
    return load_nodes_state("mysensors/power_sensor_state.json")


@pytest.fixture
def power_sensor(gateway_nodes: dict[int, Sensor], power_sensor_state: dict) -> Sensor:
    """Load the power sensor."""
    nodes = update_gateway_nodes(gateway_nodes, power_sensor_state)
    node = nodes[1]
    return node


@pytest.fixture(name="energy_sensor_state", scope="session")
def energy_sensor_state_fixture() -> dict:
    """Load the energy sensor state."""
    return load_nodes_state("mysensors/energy_sensor_state.json")


@pytest.fixture
def energy_sensor(
    gateway_nodes: dict[int, Sensor], energy_sensor_state: dict
) -> Sensor:
    """Load the energy sensor."""
    nodes = update_gateway_nodes(gateway_nodes, energy_sensor_state)
    node = nodes[1]
    return node


@pytest.fixture(name="sound_sensor_state", scope="session")
def sound_sensor_state_fixture() -> dict:
    """Load the sound sensor state."""
    return load_nodes_state("mysensors/sound_sensor_state.json")


@pytest.fixture
def sound_sensor(gateway_nodes: dict[int, Sensor], sound_sensor_state: dict) -> Sensor:
    """Load the sound sensor."""
    nodes = update_gateway_nodes(gateway_nodes, sound_sensor_state)
    node = nodes[1]
    return node


@pytest.fixture(name="distance_sensor_state", scope="session")
def distance_sensor_state_fixture() -> dict:
    """Load the distance sensor state."""
    return load_nodes_state("mysensors/distance_sensor_state.json")


@pytest.fixture
def distance_sensor(
    gateway_nodes: dict[int, Sensor], distance_sensor_state: dict
) -> Sensor:
    """Load the distance sensor."""
    nodes = update_gateway_nodes(gateway_nodes, distance_sensor_state)
    node = nodes[1]
    return node


@pytest.fixture(name="temperature_sensor_state", scope="session")
def temperature_sensor_state_fixture() -> dict:
    """Load the temperature sensor state."""
    return load_nodes_state("mysensors/temperature_sensor_state.json")


@pytest.fixture
def temperature_sensor(
    gateway_nodes: dict[int, Sensor], temperature_sensor_state: dict
) -> Sensor:
    """Load the temperature sensor."""
    nodes = update_gateway_nodes(gateway_nodes, temperature_sensor_state)
    node = nodes[1]
    return node
