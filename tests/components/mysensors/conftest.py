"""Provide common mysensors fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Generator
from copy import deepcopy
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from mysensors import BaseSyncGateway
from mysensors.persistence import MySensorsJSONDecoder
from mysensors.sensor import Sensor
import pytest

from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mysensors.config_flow import DEFAULT_BAUD_RATE
from homeassistant.components.mysensors.const import (
    CONF_BAUD_RATE,
    CONF_GATEWAY_TYPE,
    CONF_GATEWAY_TYPE_SERIAL,
    CONF_VERSION,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


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
    with (
        patch(
            "mysensors.gateway_serial.AsyncTransport", autospec=True
        ) as transport_class,
        patch("mysensors.task.OTAFirmware", autospec=True),
        patch("mysensors.task.load_fw", autospec=True),
        patch(
            "mysensors.task.Persistence",
            autospec=True,
        ) as persistence_class,
    ):
        persistence = persistence_class.return_value

        mock_gateway_features(persistence, transport_class, gateway_nodes)

        yield transport_class


def mock_gateway_features(
    persistence: MagicMock, transport_class: MagicMock, nodes: dict[int, Sensor]
) -> None:
    """Mock the gateway features."""

    async def mock_schedule_save_sensors() -> None:
        """Load nodes from via persistence."""
        gateway = transport_class.call_args[0][0]
        gateway.sensors.update(nodes)

    persistence.schedule_save_sensors = AsyncMock(
        side_effect=mock_schedule_save_sensors
    )
    # For some reason autospeccing does not recognize these methods.
    persistence.safe_load_sensors = MagicMock()
    persistence.save_sensors = MagicMock()

    async def mock_connect() -> None:
        """Mock the start method."""
        transport.connect_task = MagicMock()
        gateway = transport_class.call_args[0][0]
        gateway.on_conn_made(gateway)

    transport = transport_class.return_value
    transport.connect_task = None
    transport.connect.side_effect = mock_connect


@pytest.fixture(name="transport")
def transport_fixture(serial_transport: MagicMock) -> MagicMock:
    """Return the default mocked transport."""
    return serial_transport


@pytest.fixture
def transport_write(transport: MagicMock) -> MagicMock:
    """Return the transport mock that accepts string messages."""
    return transport.return_value.send


@pytest.fixture(name="serial_entry")
async def serial_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Create a config entry for a serial gateway."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_GATEWAY_TYPE: CONF_GATEWAY_TYPE_SERIAL,
            CONF_VERSION: "2.3",
            CONF_DEVICE: "/test/device",
            CONF_BAUD_RATE: DEFAULT_BAUD_RATE,
        },
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(serial_entry: MockConfigEntry) -> MockConfigEntry:
    """Provide the config entry used for integration set up."""
    return serial_entry


@pytest.fixture(name="integration")
async def integration_fixture(
    hass: HomeAssistant, transport: MagicMock, config_entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry, None]:
    """Set up the mysensors integration with a config entry."""
    config: dict[str, Any] = {}
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.mysensors.device.Debouncer", autospec=True
    ) as debouncer_class:

        def debouncer(
            *args: Any, function: Callable | None = None, **kwargs: Any
        ) -> MagicMock:
            """Mock the debouncer."""

            async def call_debouncer():
                """Mock call to debouncer."""
                if function is not None:
                    function()

            debounce_instance = MagicMock()
            debounce_instance.async_call.side_effect = call_debouncer
            return debounce_instance

        debouncer_class.side_effect = debouncer

        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield config_entry


@pytest.fixture
def receive_message(
    transport: MagicMock, integration: MockConfigEntry
) -> Callable[[str], None]:
    """Receive a message for the gateway."""

    def receive_message_callback(message_string: str) -> None:
        """Receive a message with the transport.

        The message_string parameter is a string in the MySensors message format.
        """
        gateway = transport.call_args[0][0]
        # node_id;child_id;command;ack;type;payload\n
        gateway.logic(message_string)

    return receive_message_callback


@pytest.fixture(name="gateway")
def gateway_fixture(
    transport: MagicMock, integration: MockConfigEntry
) -> BaseSyncGateway:
    """Return a setup gateway."""
    return transport.call_args[0][0]


def load_nodes_state(fixture_path: str) -> dict:
    """Load mysensors nodes fixture."""
    return json.loads(
        load_fixture(fixture_path, integration=DOMAIN), cls=MySensorsJSONDecoder
    )


def update_gateway_nodes(
    gateway_nodes: dict[int, Sensor], nodes: dict[int, Sensor]
) -> dict:
    """Update the gateway nodes."""
    gateway_nodes.update(nodes)
    return nodes


@pytest.fixture(name="cover_node_binary_state", scope="package")
def cover_node_binary_state_fixture() -> dict:
    """Load the cover node state."""
    return load_nodes_state("cover_node_binary_state.json")


@pytest.fixture
def cover_node_binary(
    gateway_nodes: dict[int, Sensor], cover_node_binary_state: dict
) -> Sensor:
    """Load the cover child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(cover_node_binary_state))
    return nodes[1]


@pytest.fixture(name="cover_node_percentage_state", scope="package")
def cover_node_percentage_state_fixture() -> dict:
    """Load the cover node state."""
    return load_nodes_state("cover_node_percentage_state.json")


@pytest.fixture
def cover_node_percentage(
    gateway_nodes: dict[int, Sensor], cover_node_percentage_state: dict
) -> Sensor:
    """Load the cover child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(cover_node_percentage_state))
    return nodes[1]


@pytest.fixture(name="door_sensor_state", scope="package")
def door_sensor_state_fixture() -> dict:
    """Load the door sensor state."""
    return load_nodes_state("door_sensor_state.json")


@pytest.fixture
def door_sensor(gateway_nodes: dict[int, Sensor], door_sensor_state: dict) -> Sensor:
    """Load the door sensor."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(door_sensor_state))
    return nodes[1]


@pytest.fixture(name="gps_sensor_state", scope="package")
def gps_sensor_state_fixture() -> dict:
    """Load the gps sensor state."""
    return load_nodes_state("gps_sensor_state.json")


@pytest.fixture
def gps_sensor(gateway_nodes: dict[int, Sensor], gps_sensor_state: dict) -> Sensor:
    """Load the gps sensor."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(gps_sensor_state))
    return nodes[1]


@pytest.fixture(name="dimmer_node_state", scope="package")
def dimmer_node_state_fixture() -> dict:
    """Load the dimmer node state."""
    return load_nodes_state("dimmer_node_state.json")


@pytest.fixture
def dimmer_node(gateway_nodes: dict[int, Sensor], dimmer_node_state: dict) -> Sensor:
    """Load the dimmer child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(dimmer_node_state))
    return nodes[1]


@pytest.fixture(name="hvac_node_auto_state", scope="package")
def hvac_node_auto_state_fixture() -> dict:
    """Load the hvac node auto state."""
    return load_nodes_state("hvac_node_auto_state.json")


@pytest.fixture
def hvac_node_auto(
    gateway_nodes: dict[int, Sensor], hvac_node_auto_state: dict
) -> Sensor:
    """Load the hvac auto child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(hvac_node_auto_state))
    return nodes[1]


@pytest.fixture(name="hvac_node_cool_state", scope="package")
def hvac_node_cool_state_fixture() -> dict:
    """Load the hvac node cool state."""
    return load_nodes_state("hvac_node_cool_state.json")


@pytest.fixture
def hvac_node_cool(
    gateway_nodes: dict[int, Sensor], hvac_node_cool_state: dict
) -> Sensor:
    """Load the hvac cool child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(hvac_node_cool_state))
    return nodes[1]


@pytest.fixture(name="hvac_node_heat_state", scope="package")
def hvac_node_heat_state_fixture() -> dict:
    """Load the hvac node heat state."""
    return load_nodes_state("hvac_node_heat_state.json")


@pytest.fixture
def hvac_node_heat(
    gateway_nodes: dict[int, Sensor], hvac_node_heat_state: dict
) -> Sensor:
    """Load the hvac heat child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(hvac_node_heat_state))
    return nodes[1]


@pytest.fixture(name="power_sensor_state", scope="package")
def power_sensor_state_fixture() -> dict:
    """Load the power sensor state."""
    return load_nodes_state("power_sensor_state.json")


@pytest.fixture
def power_sensor(gateway_nodes: dict[int, Sensor], power_sensor_state: dict) -> Sensor:
    """Load the power sensor."""
    nodes = update_gateway_nodes(gateway_nodes, power_sensor_state)
    return nodes[1]


@pytest.fixture(name="rgb_node_state", scope="package")
def rgb_node_state_fixture() -> dict:
    """Load the rgb node state."""
    return load_nodes_state("rgb_node_state.json")


@pytest.fixture
def rgb_node(gateway_nodes: dict[int, Sensor], rgb_node_state: dict) -> Sensor:
    """Load the rgb child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(rgb_node_state))
    return nodes[1]


@pytest.fixture(name="rgbw_node_state", scope="package")
def rgbw_node_state_fixture() -> dict:
    """Load the rgbw node state."""
    return load_nodes_state("rgbw_node_state.json")


@pytest.fixture
def rgbw_node(gateway_nodes: dict[int, Sensor], rgbw_node_state: dict) -> Sensor:
    """Load the rgbw child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(rgbw_node_state))
    return nodes[1]


@pytest.fixture(name="energy_sensor_state", scope="package")
def energy_sensor_state_fixture() -> dict:
    """Load the energy sensor state."""
    return load_nodes_state("energy_sensor_state.json")


@pytest.fixture
def energy_sensor(
    gateway_nodes: dict[int, Sensor], energy_sensor_state: dict
) -> Sensor:
    """Load the energy sensor."""
    nodes = update_gateway_nodes(gateway_nodes, energy_sensor_state)
    return nodes[1]


@pytest.fixture(name="sound_sensor_state", scope="package")
def sound_sensor_state_fixture() -> dict:
    """Load the sound sensor state."""
    return load_nodes_state("sound_sensor_state.json")


@pytest.fixture
def sound_sensor(gateway_nodes: dict[int, Sensor], sound_sensor_state: dict) -> Sensor:
    """Load the sound sensor."""
    nodes = update_gateway_nodes(gateway_nodes, sound_sensor_state)
    return nodes[1]


@pytest.fixture(name="distance_sensor_state", scope="package")
def distance_sensor_state_fixture() -> dict:
    """Load the distance sensor state."""
    return load_nodes_state("distance_sensor_state.json")


@pytest.fixture
def distance_sensor(
    gateway_nodes: dict[int, Sensor], distance_sensor_state: dict
) -> Sensor:
    """Load the distance sensor."""
    nodes = update_gateway_nodes(gateway_nodes, distance_sensor_state)
    return nodes[1]


@pytest.fixture(name="ir_transceiver_state", scope="package")
def ir_transceiver_state_fixture() -> dict:
    """Load the ir transceiver state."""
    return load_nodes_state("ir_transceiver_state.json")


@pytest.fixture
def ir_transceiver(
    gateway_nodes: dict[int, Sensor], ir_transceiver_state: dict
) -> Sensor:
    """Load the ir transceiver child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(ir_transceiver_state))
    return nodes[1]


@pytest.fixture(name="relay_node_state", scope="package")
def relay_node_state_fixture() -> dict:
    """Load the relay node state."""
    return load_nodes_state("relay_node_state.json")


@pytest.fixture
def relay_node(gateway_nodes: dict[int, Sensor], relay_node_state: dict) -> Sensor:
    """Load the relay child node."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(relay_node_state))
    return nodes[1]


@pytest.fixture(name="temperature_sensor_state", scope="package")
def temperature_sensor_state_fixture() -> dict:
    """Load the temperature sensor state."""
    return load_nodes_state("temperature_sensor_state.json")


@pytest.fixture
def temperature_sensor(
    gateway_nodes: dict[int, Sensor], temperature_sensor_state: dict
) -> Sensor:
    """Load the temperature sensor."""
    nodes = update_gateway_nodes(gateway_nodes, temperature_sensor_state)
    return nodes[1]


@pytest.fixture(name="text_node_state", scope="package")
def text_node_state_fixture() -> dict:
    """Load the text node state."""
    return load_nodes_state("text_node_state.json")


@pytest.fixture
def text_node(gateway_nodes: dict[int, Sensor], text_node_state: dict) -> Sensor:
    """Load the text child node."""
    nodes = update_gateway_nodes(gateway_nodes, text_node_state)
    return nodes[1]


@pytest.fixture(name="battery_sensor_state", scope="package")
def battery_sensor_state_fixture() -> dict:
    """Load the battery sensor state."""
    return load_nodes_state("battery_sensor_state.json")


@pytest.fixture
def battery_sensor(
    gateway_nodes: dict[int, Sensor], battery_sensor_state: dict
) -> Sensor:
    """Load the battery sensor."""
    nodes = update_gateway_nodes(gateway_nodes, deepcopy(battery_sensor_state))
    return nodes[1]
