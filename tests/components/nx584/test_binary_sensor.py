"""The tests for the nx584 sensor platform."""
from unittest import mock

from nx584 import client as nx584_client
import pytest
import requests

from homeassistant.components.nx584 import binary_sensor as nx584
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DEFAULT_CONFIG = {
    "host": nx584.DEFAULT_HOST,
    "port": nx584.DEFAULT_PORT,
    "exclude_zones": [],
    "zone_types": {},
}


class StopMe(Exception):
    """Stop helper."""


@pytest.fixture
def fake_zones():
    """Fixture for fake zones.

    Returns:
        list: List of fake zones

    """
    return [
        {"name": "front", "number": 1},
        {"name": "back", "number": 2},
        {"name": "inside", "number": 3},
    ]


@pytest.fixture
def client(fake_zones):
    """Fixture for client.

    Args:
        fake_zones (list): Fixture of fake zones

    Yields:
        MagicMock: Client Mock

    """
    with mock.patch.object(nx584_client, "Client") as _mock_client:
        client = nx584_client.Client.return_value
        client.list_zones.return_value = fake_zones
        client.get_version.return_value = "1.1"

        yield _mock_client


@pytest.mark.usefixtures("client")
@mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher")
@mock.patch("homeassistant.components.nx584.binary_sensor.NX584ZoneSensor")
def test_nx584_sensor_setup_defaults(
    mock_nx, mock_watcher, hass: HomeAssistant, fake_zones
) -> None:
    """Test the setup with no configuration."""
    add_entities = mock.MagicMock()
    config = DEFAULT_CONFIG
    nx584.setup_platform(hass, config, add_entities)
    mock_nx.assert_has_calls([mock.call(zone, "opening") for zone in fake_zones])
    assert add_entities.called
    assert nx584_client.Client.call_count == 1
    assert nx584_client.Client.call_args == mock.call("http://localhost:5007")


@pytest.mark.usefixtures("client")
@mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher")
@mock.patch("homeassistant.components.nx584.binary_sensor.NX584ZoneSensor")
def test_nx584_sensor_setup_full_config(
    mock_nx, mock_watcher, hass: HomeAssistant, fake_zones
) -> None:
    """Test the setup with full configuration."""
    config = {
        "host": "foo",
        "port": 123,
        "exclude_zones": [2],
        "zone_types": {3: "motion"},
    }
    add_entities = mock.MagicMock()
    nx584.setup_platform(hass, config, add_entities)
    mock_nx.assert_has_calls(
        [
            mock.call(fake_zones[0], "opening"),
            mock.call(fake_zones[2], "motion"),
        ]
    )
    assert add_entities.called
    assert nx584_client.Client.call_count == 1
    assert nx584_client.Client.call_args == mock.call("http://foo:123")
    assert mock_watcher.called


async def _test_assert_graceful_fail(hass, config):
    """Test the failing."""
    assert not await async_setup_component(hass, "nx584", config)


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize(
    "config",
    [
        ({"exclude_zones": ["a"]}),
        ({"zone_types": {"a": "b"}}),
        ({"zone_types": {1: "notatype"}}),
        ({"zone_types": {"notazone": "motion"}}),
    ],
)
async def test_nx584_sensor_setup_bad_config(hass: HomeAssistant, config) -> None:
    """Test the setup with bad configuration."""
    await _test_assert_graceful_fail(hass, config)


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize(
    "exception_type",
    [
        pytest.param(requests.exceptions.ConnectionError, id="connect_failed"),
        pytest.param(IndexError, id="no_partitions"),
    ],
)
async def test_nx584_sensor_setup_with_exceptions(
    hass: HomeAssistant, exception_type
) -> None:
    """Test the setup handles exceptions."""
    nx584_client.Client.return_value.list_zones.side_effect = exception_type
    await _test_assert_graceful_fail(hass, {})


@pytest.mark.usefixtures("client")
async def test_nx584_sensor_setup_version_too_old(hass: HomeAssistant) -> None:
    """Test if version is too old."""
    nx584_client.Client.return_value.get_version.return_value = "1.0"
    await _test_assert_graceful_fail(hass, {})


@pytest.mark.usefixtures("client")
def test_nx584_sensor_setup_no_zones(hass: HomeAssistant) -> None:
    """Test the setup with no zones."""
    nx584_client.Client.return_value.list_zones.return_value = []
    add_entities = mock.MagicMock()
    nx584.setup_platform(
        hass,
        DEFAULT_CONFIG,
        add_entities,
    )
    assert not add_entities.called


def test_nx584_zone_sensor_normal() -> None:
    """Test for the NX584 zone sensor."""
    zone = {"number": 1, "name": "foo", "state": True}
    sensor = nx584.NX584ZoneSensor(zone, "motion")
    assert sensor.name == "foo"
    assert not sensor.should_poll
    assert sensor.is_on
    assert sensor.extra_state_attributes["zone_number"] == 1
    assert not sensor.extra_state_attributes["bypassed"]

    zone["state"] = False
    assert not sensor.is_on


def test_nx584_zone_sensor_bypassed() -> None:
    """Test for the NX584 zone sensor."""
    zone = {"number": 1, "name": "foo", "state": True, "bypassed": True}
    sensor = nx584.NX584ZoneSensor(zone, "motion")
    assert sensor.name == "foo"
    assert not sensor.should_poll
    assert sensor.is_on
    assert sensor.extra_state_attributes["zone_number"] == 1
    assert sensor.extra_state_attributes["bypassed"]

    zone["state"] = False
    zone["bypassed"] = False
    assert not sensor.is_on
    assert not sensor.extra_state_attributes["bypassed"]


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_process_zone_event(mock_update) -> None:
    """Test the processing of zone events."""
    zone1 = {"number": 1, "name": "foo", "state": True}
    zone2 = {"number": 2, "name": "bar", "state": True}
    zones = {
        1: nx584.NX584ZoneSensor(zone1, "motion"),
        2: nx584.NX584ZoneSensor(zone2, "motion"),
    }
    watcher = nx584.NX584Watcher(None, zones)
    watcher._process_zone_event({"zone": 1, "zone_state": False})
    assert not zone1["state"]
    assert mock_update.call_count == 1


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_process_zone_event_missing_zone(mock_update) -> None:
    """Test the processing of zone events with missing zones."""
    watcher = nx584.NX584Watcher(None, {})
    watcher._process_zone_event({"zone": 1, "zone_state": False})
    assert not mock_update.called


def test_nx584_watcher_run_with_zone_events() -> None:
    """Test the zone events."""
    empty_me = [1, 2]

    def fake_get_events():
        """Return nothing twice, then some events."""
        if empty_me:
            empty_me.pop()
        else:
            return fake_events

    client = mock.MagicMock()
    fake_events = [
        {"zone": 1, "zone_state": True, "type": "zone_status"},
        {"zone": 2, "foo": False},
    ]
    client.get_events.side_effect = fake_get_events
    watcher = nx584.NX584Watcher(client, {})

    @mock.patch.object(watcher, "_process_zone_event")
    def run(fake_process):
        """Run a fake process."""
        fake_process.side_effect = StopMe
        with pytest.raises(StopMe):
            watcher._run()
        assert fake_process.call_count == 1
        assert fake_process.call_args == mock.call(fake_events[0])

    run()
    assert client.get_events.call_count == 3


@mock.patch("time.sleep")
def test_nx584_watcher_run_retries_failures(mock_sleep) -> None:
    """Test the retries with failures."""
    empty_me = [1, 2]

    def fake_run():
        """Fake runner."""
        if empty_me:
            empty_me.pop()
            raise requests.exceptions.ConnectionError()
        raise StopMe()

    watcher = nx584.NX584Watcher(None, {})
    with mock.patch.object(watcher, "_run") as mock_inner:
        mock_inner.side_effect = fake_run
        with pytest.raises(StopMe):
            watcher.run()
        assert mock_inner.call_count == 3
    mock_sleep.assert_has_calls([mock.call(10), mock.call(10)])
