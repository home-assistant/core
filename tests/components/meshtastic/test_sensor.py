"""Tests for the Meshtastic sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.meshtastic.const import (
    DOMAIN,
    REBOOT_GRACE,
    gateway_unique_id,
    node_unique_id,
)
from homeassistant.components.meshtastic.models import MeshtasticData
from homeassistant.components.meshtastic.sensor import GATEWAY_SENSORS, NODE_SENSORS
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfDensity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    SENSOR_NODE_ID,
    SENSOR_NODE_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, snapshot_platform

#: Six minutes after the newest timestamp in ``nodes.json``, so every node in
#: the fixture counts as recently heard.
FROZEN_TIME = "2025-09-08T03:06:00+00:00"

GATEWAY_BATTERY = "sensor.ha_gateway_battery"
GATEWAY_CONNECTION_STATE = "sensor.ha_gateway_connection_state"
GATEWAY_KNOWN_NODES = "sensor.ha_gateway_known_nodes"
GATEWAY_LAST_PACKET = "sensor.ha_gateway_last_packet_received"
GATEWAY_NODEDB = "sensor.ha_gateway_node_database_entries"
GATEWAY_UPTIME = "sensor.ha_gateway_uptime"
GATEWAY_VOLTAGE = "sensor.ha_gateway_voltage"
GATEWAY_FREE_MEMORY = "sensor.ha_gateway_free_memory"
GATEWAY_ONLINE_NODES = "sensor.ha_gateway_online_nodes"
REMOTE_BATTERY = "sensor.remote_one_battery"
REMOTE_LAST_HEARD = "sensor.remote_one_last_heard"
REMOTE_SNR = "sensor.remote_one_snr"
SENSOR_NODE_TEMPERATURE = "sensor.weather_shed_temperature"
SENSOR_NODE_CO2 = "sensor.weather_shed_carbon_dioxide"

#: One reading of every metric the platform knows about, keyed by the library's
#: camelCase telemetry group.  Injected as separate packets, because the
#: library only ever puts one group in a packet.
TELEMETRY_GROUPS: dict[str, dict[str, Any]] = {
    "deviceMetrics": {
        "batteryLevel": 72,
        "voltage": 3.94,
        "channelUtilization": 4.5,
        "airUtilTx": 0.35,
        "uptimeSeconds": 3600,
    },
    "environmentMetrics": {
        "temperature": 19.5,
        "relativeHumidity": 55.0,
        "barometricPressure": 1008.75,
        "gasResistance": 96.25,
        "iaq": 37,
        "lux": 480.0,
        "whiteLux": 512.0,
        "irLux": 64.0,
        "uvLux": 8.0,
        "windSpeed": 3.4,
        "windDirection": 225,
        "windGust": 7.1,
        "windLull": 1.2,
        "voltage": 12.4,
        "current": 0.85,
        "distance": 1250,
        "weight": 24.75,
        "radiation": 11.5,
        "rainfall1h": 2.5,
        "rainfall24h": 17.5,
        "soilMoisture": 41,
        "soilTemperature": 14.25,
    },
    "powerMetrics": {
        "ch1Voltage": 4.05,
        "ch1Current": 120.5,
        "ch2Voltage": 12.1,
        "ch2Current": 45.25,
        "ch3Voltage": 5.02,
        "ch3Current": 8.75,
    },
    "airQualityMetrics": {
        "pm10Standard": 4,
        "pm25Standard": 9,
        "pm40Standard": 11,
        "pm100Standard": 14,
        "co2": 615,
        "pmVocIdx": 105,
        "pmNoxIdx": 3,
    },
}

#: The gateway's own link statistics, which only ever come from the node
#: Home Assistant is connected to.
LOCAL_STATS = {
    "numOnlineNodes": 4,
    "numTotalNodes": 11,
    "heapFreeBytes": 51200,
    "heapTotalBytes": 204800,
    "numPacketsTx": 312,
    "numPacketsRx": 918,
    "numPacketsRxBad": 7,
    "numRxDupe": 21,
    "numTxRelay": 64,
    "numTxRelayCanceled": 5,
    "numTxDropped": 2,
    "noiseFloor": -98,
}


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Pin the clock so node timestamps are deterministic."""
    freezer.move_to(FROZEN_TIME)


def _telemetry_packet(
    node_num: int, node_id: str, group: str, metrics: dict[str, Any]
) -> dict[str, Any]:
    """Return a telemetry packet as the library hands it over."""
    return {
        "from": node_num,
        "to": 4294967295,
        "fromId": node_id,
        "toId": "^all",
        "channel": 0,
        "id": 900000000 + node_num % 1000,
        "rxTime": 1757300420,
        "rxSnr": 4.25,
        "rxRssi": -92,
        "hopLimit": 3,
        "hopStart": 3,
        "decoded": {
            "portnum": "TELEMETRY_APP",
            "telemetry": {"time": 1757300419, group: metrics},
        },
    }


async def _setup_with_nodes(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up the sensor platform and push the sample node database."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, entry)
    for node in node_fixtures.values():
        await inject_node_info(hass, pubsub, interface, node)


async def _inject_all_telemetry(
    hass: HomeAssistant, pubsub: FakePubSub, interface: MagicMock
) -> None:
    """Report every metric the platform knows about, from the sample nodes."""
    for group, metrics in TELEMETRY_GROUPS.items():
        await inject_packet(
            hass,
            pubsub,
            interface,
            _telemetry_packet(SENSOR_NODE_NUM, SENSOR_NODE_ID, group, metrics),
        )
    await inject_packet(
        hass,
        pubsub,
        interface,
        _telemetry_packet(GATEWAY_NUM, GATEWAY_ID, "localStats", LOCAL_STATS),
    )


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors and devices created for the sample mesh."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    assert dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ) == snapshot(name="devices")


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
async def test_every_description_reports_a_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that every sensor exists once its metric has been reported.

    The telemetry families are a long list of protobuf fields; this is what
    catches a metric spelled differently in the description than the library
    spells it, which would leave the sensor silently missing.
    """
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    await _inject_all_telemetry(hass, mock_pubsub, mock_meshtastic_client)

    unique_ids = [
        node_unique_id(GATEWAY_NUM, SENSOR_NODE_NUM, description.key)
        for description in NODE_SENSORS
    ] + [
        gateway_unique_id(GATEWAY_NUM, description.key)
        for description in GATEWAY_SENSORS
        # The gateway runs off USB in the fixture, so it reports no charge.
        if description.key != "battery_level"
    ]
    for unique_id in unique_ids:
        entity_id = entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, unique_id
        )
        assert entity_id is not None, f"no entity for {unique_id}"
        assert (state := hass.states.get(entity_id)), unique_id
        assert state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE), unique_id


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "value", "unit", "device_class", "state_class"),
    [
        (
            SENSOR_NODE_TEMPERATURE,
            "19.5",
            "°C",
            SensorDeviceClass.TEMPERATURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.weather_shed_humidity",
            "55.0",
            "%",
            SensorDeviceClass.HUMIDITY,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.weather_shed_atmospheric_pressure",
            "1008.75",
            "hPa",
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            SensorStateClass.MEASUREMENT,
        ),
        (
            SENSOR_NODE_CO2,
            "615",
            "ppm",
            SensorDeviceClass.CO2,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.weather_shed_pm1",
            "4",
            UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
            SensorDeviceClass.PM1,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.weather_shed_wind_direction",
            "225",
            "°",
            SensorDeviceClass.WIND_DIRECTION,
            SensorStateClass.MEASUREMENT_ANGLE,
        ),
        (
            "sensor.weather_shed_channel_1_current",
            "120.5",
            "mA",
            SensorDeviceClass.CURRENT,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.weather_shed_rainfall_last_hour",
            "2.5",
            "mm",
            SensorDeviceClass.PRECIPITATION,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.weather_shed_gas_resistance",
            "96.25",
            "MΩ",
            None,
            SensorStateClass.MEASUREMENT,
        ),
        (
            GATEWAY_ONLINE_NODES,
            "4",
            None,
            None,
            SensorStateClass.MEASUREMENT,
        ),
        (
            "sensor.ha_gateway_packets_received",
            "918",
            None,
            None,
            SensorStateClass.TOTAL_INCREASING,
        ),
        (
            "sensor.ha_gateway_noise_floor",
            "-98",
            "dBm",
            SensorDeviceClass.SIGNAL_STRENGTH,
            SensorStateClass.MEASUREMENT,
        ),
    ],
)
async def test_units_and_device_classes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_id: str,
    value: str,
    unit: str | None,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass,
) -> None:
    """Test that each metric is published with the right unit and class."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    await _inject_all_telemetry(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(entity_id))
    assert state.state == value
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert state.attributes.get(ATTR_STATE_CLASS) == state_class


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
async def test_byte_counts_are_shown_in_kilobytes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the heap sensors convert to a unit a human can read."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    await _inject_all_telemetry(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(GATEWAY_FREE_MEMORY))
    assert state.state == "51.2"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "kB"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_SIZE


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_gateway_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the sensors that describe the node Home Assistant is talking to."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(GATEWAY_CONNECTION_STATE))
    assert state.state == "connected"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes["options"] == [
        "disconnected",
        "connecting",
        "connected",
        "reconnecting",
        "circuit_open",
    ]

    # Three nodes introduced themselves; the gateway is one of them.
    assert (state := hass.states.get(GATEWAY_KNOWN_NODES))
    assert state.state == "3"
    assert (state := hass.states.get(GATEWAY_NODEDB))
    assert state.state == "3"

    # The gateway reported 431 seconds of uptime at the frozen time.
    assert (state := hass.states.get(GATEWAY_UPTIME))
    assert state.state == "2025-09-08T02:58:49+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.UPTIME

    # The newest last_heard in the mesh, which is the gateway's own.
    assert (state := hass.states.get(GATEWAY_LAST_PACKET))
    assert state.state == "2025-09-08T03:06:00+00:00"

    assert (state := hass.states.get(GATEWAY_VOLTAGE))
    assert state.state == "4.19"


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the sensors that describe another node of the mesh."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(REMOTE_SNR))
    assert state.state == "5.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "dB"
    assert (state := hass.states.get(REMOTE_BATTERY))
    assert state.state == "55"
    assert (state := hass.states.get(REMOTE_LAST_HEARD))
    assert state.state == "2025-09-08T03:01:20+00:00"
    assert (state := hass.states.get(SENSOR_NODE_TEMPERATURE))
    assert state.state == "21.5"

    # A telemetry sensor only exists once the node reported that metric, and
    # the weather shed has never sent device metrics.
    assert hass.states.get("sensor.weather_shed_battery") is None


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_unknown_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the readings that have to be reported as unknown rather than wrong.

    The firmware sends 101 % for a node that runs off USB and has no battery,
    and it can send a metric of a type that is not a number at all; neither is
    a charge level and neither may be published as one.
    """
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(GATEWAY_BATTERY))
    assert state.state == STATE_UNKNOWN

    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _telemetry_packet(
            SENSOR_NODE_NUM,
            SENSOR_NODE_ID,
            "deviceMetrics",
            {"batteryLevel": 66, "voltage": "not a number", "uptimeSeconds": True},
        ),
    )

    assert (state := hass.states.get("sensor.weather_shed_battery"))
    assert state.state == "66"
    assert (state := hass.states.get("sensor.weather_shed_voltage"))
    assert state.state == STATE_UNKNOWN
    # A boolean is not an uptime, so there is no boot time to derive.
    assert (state := hass.states.get("sensor.weather_shed_uptime"))
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_gateway_sensors_without_a_node_record(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the gateway sensors cope with an empty node table.

    The gateway's own metrics are read out of the node table, which the mesh
    can empty at any time; that must read as unknown, not raise.
    """
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_set_updated_data(
        MeshtasticData(gateway=coordinator.gateway, nodes={})
    )
    await hass.async_block_till_done()

    for entity_id in (
        GATEWAY_BATTERY,
        GATEWAY_VOLTAGE,
        GATEWAY_UPTIME,
        GATEWAY_LAST_PACKET,
    ):
        assert (state := hass.states.get(entity_id)), entity_id
        assert state.state == STATE_UNKNOWN, entity_id

    assert (state := hass.states.get(GATEWAY_KNOWN_NODES))
    assert state.state == "0"
    # The link itself is still up, so the link diagnostic still reports.
    assert (state := hass.states.get(GATEWAY_CONNECTION_STATE))
    assert state.state == "connected"


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_availability_while_the_link_is_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that losing the link makes the readings unavailable, not stale."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert hass.states.get(GATEWAY_LAST_PACKET).state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(GATEWAY_LAST_PACKET))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(REMOTE_SNR))
    assert state.state == STATE_UNAVAILABLE
    # The link diagnostic is the one thing worth reading while it is down.
    assert (state := hass.states.get(GATEWAY_CONNECTION_STATE))
    assert state.state == "reconnecting"


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_availability_during_the_reboot_grace_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a reboot we asked for does not flap every sensor.

    A node that was told to reboot is back within a minute; making every
    entity unavailable and then available again in the meantime is noise.
    """
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    runtime = mock_config_entry.runtime_data
    runtime.client.async_note_reboot_expected()

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert not runtime.coordinator.last_update_success
    assert (state := hass.states.get(GATEWAY_LAST_PACKET))
    assert state.state != STATE_UNAVAILABLE
    assert (state := hass.states.get(REMOTE_SNR))
    assert state.state != STATE_UNAVAILABLE

    # Once the window closes without the node coming back, it is unavailable.
    freezer.tick(timedelta(seconds=REBOOT_GRACE + 1))
    runtime.coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert (state := hass.states.get(GATEWAY_LAST_PACKET))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_forgotten_by_the_mesh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node dropping out of the table makes its sensors unavailable."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert hass.states.get(REMOTE_SNR).state == "5.5"

    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_set_updated_data(
        MeshtasticData(
            gateway=coordinator.gateway,
            nodes={GATEWAY_ID: coordinator.data.nodes[GATEWAY_ID]},
        )
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(REMOTE_SNR))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_discovered_at_runtime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a node heard after setup gets sensors without a reload.

    A metric can also start being reported long after the node first turned
    up, so the platform re-checks the whole table rather than only new nodes.
    """
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(REMOTE_SNR) is None

    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )

    assert (state := hass.states.get(REMOTE_SNR))
    assert state.state == "5.5"
    assert hass.states.get(SENSOR_NODE_TEMPERATURE) is None

    # A device of its own, hung off the gateway.
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{GATEWAY_ID}_{REMOTE_ID}"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.via_device_id is not None

    # A metric this node had never reported turns up later.
    assert hass.states.get("sensor.remote_one_temperature") is None
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        _telemetry_packet(
            2864434397,
            REMOTE_ID,
            "environmentMetrics",
            {"temperature": 17.25},
        ),
    )

    assert (state := hass.states.get("sensor.remote_one_temperature"))
    assert state.state == "17.25"


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_relayed_node_gets_no_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node that only ever relayed traffic gets no sensors.

    Relayed traffic names nodes that never introduced themselves; giving each
    of them a device and a dozen entities would be an entity storm.
    """
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    before = hass.states.async_entity_ids_count(Platform.SENSOR)

    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        dict(packet_fixtures["packet_telemetry_device"]),
    )

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.data.nodes[REMOTE_ID].presumptive
    assert hass.states.async_entity_ids_count(Platform.SENSOR) == before
