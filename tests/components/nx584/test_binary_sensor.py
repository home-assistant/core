"""The tests for the nx584 sensor platform."""

from typing import Any
from unittest import mock
from unittest.mock import MagicMock

from nx584 import client as nx584_client
import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.nx584 import binary_sensor as nx584
from homeassistant.components.nx584.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST, TEST_PORT

ZONE_OPTIONS = {"exclude_zones": [2], "zone_types": {"3": "motion"}}


class StopMe(Exception):
    """Stop helper."""


async def _async_setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_client")
async def test_nx584_sensor_setup_defaults(
    hass: HomeAssistant,
    mock_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test every zone is added as an opening sensor by default."""
    await _async_setup_entry(hass, mock_config_entry)

    for entity_id in (
        "binary_sensor.front",
        "binary_sensor.back",
        "binary_sensor.inside",
    ):
        assert hass.states.get(entity_id).attributes["device_class"] == "opening"
    mock_watcher.return_value.start.assert_called_once()


@pytest.mark.usefixtures("mock_client")
async def test_nx584_sensor_setup_zone_options(
    hass: HomeAssistant, mock_watcher: MagicMock
) -> None:
    """Test the zone options apply with the string keys a stored entry has."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
        options=ZONE_OPTIONS,
    )
    await _async_setup_entry(hass, entry)

    assert hass.states.get("binary_sensor.front").attributes["device_class"] == (
        "opening"
    )
    assert hass.states.get("binary_sensor.back") is None
    assert hass.states.get("binary_sensor.inside").attributes["device_class"] == (
        "motion"
    )
    assert sorted(mock_watcher.call_args.args[1]) == [1, 3]


@pytest.mark.usefixtures("mock_client")
@pytest.mark.parametrize(
    "config",
    [
        ({"exclude_zones": ["a"]}),
        ({"zone_types": {"a": "b"}}),
        ({"zone_types": {1: "notatype"}}),
        ({"zone_types": {"notazone": "motion"}}),
    ],
)
async def test_nx584_sensor_setup_bad_config(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test an invalid YAML configuration is not imported."""
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {BINARY_SENSOR_DOMAIN: {"platform": "nx584", **config}},
    )
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []
    assert hass.config_entries.async_entries(DOMAIN) == []
    assert not nx584_client.Client.called


async def test_nx584_sensor_setup_version_too_old(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no zone sensors are added for a server that is too old."""
    mock_client.return_value.get_version.return_value = "1.0"
    await _async_setup_entry(hass, mock_config_entry)

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []
    assert not mock_watcher.called


async def test_nx584_sensor_setup_no_zones(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the setup with no zones."""
    mock_client.return_value.list_zones.return_value = []
    await _async_setup_entry(hass, mock_config_entry)

    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []
    assert not mock_watcher.called


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
def test_nx584_watcher_process_zone_event_updates_bypass(mock_update) -> None:
    """Test the processing of zone events updates bypass state."""
    zone = {"number": 1, "name": "foo", "state": True, "bypassed": False}
    zones = {1: nx584.NX584ZoneSensor(zone, "motion")}
    watcher = nx584.NX584Watcher(None, zones)

    watcher._process_zone_event(
        {"zone": 1, "zone_state": False, "zone_flags": ["Bypass"]}
    )

    assert zone["bypassed"]
    assert not zone["state"]

    watcher._process_zone_event({"zone": 1, "zone_state": True, "zone_flags": []})

    assert not zone["bypassed"]
    assert zone["state"]
    assert mock_update.call_count == 2


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_process_zone_event_missing_zone(mock_update) -> None:
    """Test the processing of zone events with missing zones."""
    watcher = nx584.NX584Watcher(None, {})
    watcher._process_zone_event({"zone": 1, "zone_state": False})
    assert not mock_update.called


def test_nx584_watcher_run_with_zone_events() -> None:
    """Test the zone events."""
    empty_me = [1, 2]

    def fake_get_events(timeout: int) -> list[dict[str, Any]] | None:
        """Return nothing twice, then some events."""
        if empty_me:
            empty_me.pop()
            return None
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
    assert (
        client.get_events.call_args_list
        == [mock.call(timeout=nx584.EVENTS_POLL_TIMEOUT)] * 3
    )


def test_nx584_watcher_run_retries_failures() -> None:
    """Test the retries with failures."""
    empty_me = [1, 2]

    def fake_run():
        """Fake runner."""
        if empty_me:
            empty_me.pop()
            raise requests.exceptions.ConnectionError
        raise StopMe

    watcher = nx584.NX584Watcher(None, {})
    with (
        mock.patch.object(watcher, "_run") as mock_inner,
        mock.patch.object(watcher._stop_event, "wait") as mock_wait,
    ):
        mock_inner.side_effect = fake_run
        with pytest.raises(StopMe):
            watcher.run()
        assert mock_inner.call_count == 3
    mock_wait.assert_has_calls([mock.call(10), mock.call(10)])


def test_nx584_watcher_stop_on_failure() -> None:
    """Test a failure caused by the stop is not reported or retried."""
    watcher = nx584.NX584Watcher(None, {})

    def fake_run() -> None:
        """Stop the watcher while a request is pending."""
        watcher.stop()
        raise requests.exceptions.ConnectionError

    with (
        mock.patch.object(watcher, "_run", side_effect=fake_run) as mock_inner,
        mock.patch.object(watcher._stop_event, "wait") as mock_wait,
        mock.patch.object(nx584, "_LOGGER") as mock_logger,
    ):
        watcher.run()

    assert mock_inner.call_count == 1
    assert not mock_wait.called
    assert not mock_logger.error.called


def test_nx584_watcher_stop() -> None:
    """Test the watcher leaves its loop once stopped."""
    client = mock.MagicMock()
    watcher = nx584.NX584Watcher(client, {})

    def fake_get_events(timeout: int) -> list[dict[str, Any]]:
        """Stop the watcher while a request is pending."""
        watcher.stop()
        return [{"zone": 1, "zone_state": True, "type": "zone_status"}]

    client.get_events.side_effect = fake_get_events
    with mock.patch.object(watcher, "_process_events") as mock_process:
        watcher.run()

    assert not mock_process.called
