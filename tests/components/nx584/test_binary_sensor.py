"""The tests for the nx584 sensor platform."""

from unittest import mock
from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.nx584 import binary_sensor as nx584
from homeassistant.components.nx584.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


class StopMe(Exception):
    """Stop helper."""


@pytest.fixture
def fake_zones() -> list[dict[str, object]]:
    """Fixture for fake zones.

    Returns:
        list: List of fake zones

    """
    return [
        {"name": "front", "number": 1, "state": False},
        {"name": "back", "number": 2, "state": False},
        {"name": "inside", "number": 3, "state": False},
    ]


@pytest.fixture
def fake_client(fake_zones: list[dict[str, object]]) -> MagicMock:
    """Fixture for a fake nx584 client."""
    client = mock.MagicMock()
    client.list_zones.return_value = fake_zones
    client.get_version.return_value = "1.1"
    return client


def test_build_zone_sensors_defaults(
    fake_client: MagicMock, fake_zones: list[dict[str, object]]
) -> None:
    """Test building zone sensors with no exclusions or overrides."""
    zone_sensors = nx584._build_zone_sensors(fake_client, [], {})

    assert set(zone_sensors) == {1, 2, 3}
    for number, sensor in zone_sensors.items():
        assert sensor.name == next(
            zone["name"] for zone in fake_zones if zone["number"] == number
        )
        assert sensor.device_class == "opening"


def test_build_zone_sensors_excludes_and_overrides(
    fake_client: MagicMock, fake_zones: list[dict[str, object]]
) -> None:
    """Test building zone sensors with exclusions and type overrides."""
    zone_sensors = nx584._build_zone_sensors(fake_client, [2], {3: "motion"})

    assert set(zone_sensors) == {1, 3}
    assert zone_sensors[1].device_class == "opening"
    assert zone_sensors[3].device_class == "motion"


def test_build_zone_sensors_connection_error(fake_client: MagicMock) -> None:
    """Test building zone sensors when the panel can't be reached."""
    fake_client.list_zones.side_effect = requests.exceptions.ConnectionError

    assert nx584._build_zone_sensors(fake_client, [], {}) is None


def test_build_zone_sensors_version_too_old(fake_client: MagicMock) -> None:
    """Test building zone sensors when the panel firmware is too old."""
    fake_client.get_version.return_value = "1.0"

    assert nx584._build_zone_sensors(fake_client, [], {}) is None


def test_build_zone_sensors_no_zones(fake_client: MagicMock) -> None:
    """Test building zone sensors when the panel reports no zones."""
    fake_client.list_zones.return_value = []

    assert nx584._build_zone_sensors(fake_client, [], {}) == {}


@pytest.mark.parametrize(
    ("reason", "issue_domain", "issue_id"),
    [
        pytest.param(
            "already_configured",
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            id="already_configured",
        ),
        pytest.param(
            "cannot_connect",
            DOMAIN,
            "deprecated_yaml_import_issue_cannot_connect",
            id="import_failed",
        ),
    ],
)
async def test_async_setup_platform_imports_config(
    hass: HomeAssistant, reason: str, issue_domain: str, issue_id: str
) -> None:
    """Test the YAML platform triggers the config entry import flow and raises an issue."""
    config = {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 5007,
        "exclude_zones": [],
        "zone_types": {},
    }

    with mock.patch(
        "homeassistant.config_entries.ConfigEntriesFlowManager.async_init",
        return_value=FlowResult(type=FlowResultType.ABORT, reason=reason),
    ) as mock_init:
        await nx584.async_setup_platform(hass, config, mock.MagicMock())

    mock_init.assert_called_once_with(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    assert ir.async_get(hass).async_get_issue(issue_domain, issue_id) is not None


async def test_async_setup_entry_creates_zone_sensors(
    hass: HomeAssistant, fake_zones: list[dict[str, object]]
) -> None:
    """Test setting up the binary_sensor platform from a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 5007},
        title="NX584",
    )
    entry.add_to_hass(hass)

    with (
        mock.patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher"),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.list_zones.return_value = fake_zones
        mock_client.list_partitions.return_value = [
            {"armed": False, "condition_flags": []}
        ]
        mock_client.get_version.return_value = "1.1"

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    for zone in fake_zones:
        assert hass.states.get(f"binary_sensor.{zone['name']}") is not None


@pytest.mark.parametrize(
    "zone_types",
    [
        pytest.param({3: "motion"}, id="python_types"),
        pytest.param(
            {"3": "motion"},
            id="json_roundtripped_types",
        ),
    ],
)
async def test_async_setup_entry_applies_options(
    hass: HomeAssistant,
    fake_zones: list[dict[str, object]],
    zone_types: dict[int | str, str],
) -> None:
    """Test the binary_sensor platform applies exclude_zones and zone_types options.

    Config entry options are persisted as JSON, so after a reload the
    zone_types keys come back as strings instead of ints.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 5007},
        options={"exclude_zones": [2], "zone_types": zone_types},
        title="NX584",
    )
    entry.add_to_hass(hass)

    with (
        mock.patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher"),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.list_zones.return_value = fake_zones
        mock_client.list_partitions.return_value = [
            {"armed": False, "condition_flags": []}
        ]
        mock_client.get_version.return_value = "1.1"

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.front") is not None
    assert hass.states.get("binary_sensor.back") is None
    assert hass.states.get("binary_sensor.inside") is not None
    assert (
        hass.states.get("binary_sensor.inside").attributes["device_class"] == "motion"
    )


async def test_async_setup_entry_stops_watcher_on_unload(
    hass: HomeAssistant, fake_zones: list[dict[str, object]]
) -> None:
    """Test the watcher thread is signalled to stop when the config entry unloads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 5007},
        title="NX584",
    )
    entry.add_to_hass(hass)

    with (
        mock.patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        mock.patch(
            "homeassistant.components.nx584.binary_sensor.NX584Watcher"
        ) as mock_watcher_cls,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.list_zones.return_value = fake_zones
        mock_client.get_version.return_value = "1.1"

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_watcher = mock_watcher_cls.return_value
        assert mock_watcher.start.called
        assert not mock_watcher.stop.called

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    mock_watcher.stop.assert_called_once()


async def test_async_setup_entry_registers_bypass_services(
    hass: HomeAssistant, fake_zones: list[dict[str, object]]
) -> None:
    """Test the bypass/unbypass services target the correct zone's client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 5007},
        title="NX584",
    )
    entry.add_to_hass(hass)

    with (
        mock.patch("homeassistant.components.nx584.client.Client") as mock_client_cls,
        mock.patch("homeassistant.components.nx584.binary_sensor.NX584Watcher"),
    ):
        mock_client = mock_client_cls.return_value
        mock_client.list_zones.return_value = fake_zones
        mock_client.list_partitions.return_value = [
            {"armed": False, "condition_flags": []}
        ]
        mock_client.get_version.return_value = "1.1"

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            DOMAIN,
            "bypass",
            {"entity_id": "binary_sensor.front"},
            blocking=True,
        )
        mock_client.set_bypass.assert_called_once_with(1, True)

        mock_client.set_bypass.reset_mock()
        await hass.services.async_call(
            DOMAIN,
            "unbypass",
            {"entity_id": "binary_sensor.front"},
            blocking=True,
        )
        mock_client.set_bypass.assert_called_once_with(1, False)


def test_nx584_zone_sensor_normal() -> None:
    """Test for the NX584 zone sensor."""
    zone = {"number": 1, "name": "foo", "state": True}
    sensor = nx584.NX584ZoneSensor(zone, "motion", mock.MagicMock())
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
    sensor = nx584.NX584ZoneSensor(zone, "motion", mock.MagicMock())
    assert sensor.name == "foo"
    assert not sensor.should_poll
    assert sensor.is_on
    assert sensor.extra_state_attributes["zone_number"] == 1
    assert sensor.extra_state_attributes["bypassed"]

    zone["state"] = False
    zone["bypassed"] = False
    assert not sensor.is_on
    assert not sensor.extra_state_attributes["bypassed"]


def test_nx584_zone_sensor_zone_bypass() -> None:
    """Test that zone_bypass calls set_bypass with True."""
    zone = {"number": 3, "name": "foo", "state": True}
    client = mock.MagicMock()
    sensor = nx584.NX584ZoneSensor(zone, "motion", client)

    sensor.zone_bypass()

    client.set_bypass.assert_called_once_with(3, True)


def test_nx584_zone_sensor_zone_unbypass() -> None:
    """Test that zone_unbypass calls set_bypass with False."""
    zone = {"number": 3, "name": "foo", "state": True}
    client = mock.MagicMock()
    sensor = nx584.NX584ZoneSensor(zone, "motion", client)

    sensor.zone_unbypass()

    client.set_bypass.assert_called_once_with(3, False)


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_process_zone_event(mock_update: MagicMock) -> None:
    """Test the processing of zone events."""
    zone1 = {"number": 1, "name": "foo", "state": True}
    zone2 = {"number": 2, "name": "bar", "state": True}
    zones = {
        1: nx584.NX584ZoneSensor(zone1, "motion", mock.MagicMock()),
        2: nx584.NX584ZoneSensor(zone2, "motion", mock.MagicMock()),
    }
    watcher = nx584.NX584Watcher(None, zones)
    watcher._process_zone_event({"zone": 1, "zone_state": False})
    assert not zone1["state"]
    assert mock_update.call_count == 1


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_process_zone_event_updates_bypass(
    mock_update: MagicMock,
) -> None:
    """Test the processing of zone events updates bypass state."""
    zone = {"number": 1, "name": "foo", "state": True, "bypassed": False}
    zones = {1: nx584.NX584ZoneSensor(zone, "motion", mock.MagicMock())}
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
def test_nx584_watcher_process_zone_event_missing_zone(mock_update: MagicMock) -> None:
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
    assert client.get_events.call_count == 3


@mock.patch("time.sleep")
def test_nx584_watcher_run_retries_failures(mock_sleep: MagicMock) -> None:
    """Test the retries with failures."""
    empty_me = [1, 2]

    def fake_run():
        """Fake runner."""
        if empty_me:
            empty_me.pop()
            raise requests.exceptions.ConnectionError
        raise StopMe

    watcher = nx584.NX584Watcher(None, {})
    with mock.patch.object(watcher, "_run") as mock_inner:
        mock_inner.side_effect = fake_run
        with pytest.raises(StopMe):
            watcher.run()
        assert mock_inner.call_count == 3
    mock_sleep.assert_has_calls([mock.call(10), mock.call(10)])


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
@mock.patch("time.sleep")
def test_nx584_watcher_run_marks_zones_unavailable_on_connection_error(
    mock_sleep: MagicMock, mock_update: MagicMock
) -> None:
    """Test zone sensors are marked unavailable when the host disconnects."""
    zone_sensor = nx584.NX584ZoneSensor(
        {"number": 1, "name": "foo", "state": False},
        "motion",
        mock.MagicMock(),
    )
    watcher = nx584.NX584Watcher(None, {1: zone_sensor})

    with mock.patch.object(watcher, "_run") as mock_inner:
        mock_inner.side_effect = [requests.exceptions.ConnectionError, StopMe]
        with pytest.raises(StopMe):
            watcher.run()

    assert zone_sensor.available is False
    assert mock_update.called


def test_nx584_watcher_stop_signals_run_loop_to_exit() -> None:
    """Test stop() causes the outer run loop to exit without polling further."""
    watcher = nx584.NX584Watcher(mock.MagicMock(), {})
    watcher.stop()

    with mock.patch.object(watcher, "_run") as mock_inner:
        watcher.run()

    assert not mock_inner.called


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_stop_signals_inner_loop_to_exit(mock_update: MagicMock) -> None:
    """Test stop() causes _run() to exit after the current poll instead of looping."""
    client = mock.MagicMock()
    client.get_events.return_value = None
    watcher = nx584.NX584Watcher(client, {})
    watcher.stop()

    watcher._run()

    # Only the initial throwaway call is made; the polling loop never runs.
    assert client.get_events.call_count == 1


@mock.patch.object(nx584.NX584ZoneSensor, "schedule_update_ha_state")
def test_nx584_watcher_run_marks_zones_available_after_reconnect(
    mock_update: MagicMock,
) -> None:
    """Test zone sensors become available again once the panel is reachable."""
    zone_sensor = nx584.NX584ZoneSensor(
        {"number": 1, "name": "foo", "state": False},
        "motion",
        mock.MagicMock(),
    )
    zone_sensor._attr_available = False

    client = mock.MagicMock()
    client.get_events.side_effect = [None, StopMe]
    watcher = nx584.NX584Watcher(client, {1: zone_sensor})

    with pytest.raises(StopMe):
        watcher._run()

    assert zone_sensor.available is True
    assert mock_update.called
