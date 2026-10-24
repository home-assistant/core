"""Test sensor platform of Ping."""

from unittest.mock import AsyncMock, Mock, patch

from icmplib import Host, NameLookupError
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
@pytest.mark.parametrize(
    "sensor_name",
    [
        "round_trip_time_average",
        "round_trip_time_maximum",
        "round_trip_time_mean_deviation",  # should be None in the snapshot
        "round_trip_time_minimum",
        "jitter",
        "packet_loss",
    ],
)
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    sensor_name: str,
) -> None:
    """Test sensor setup and update."""

    entry = entity_registry.async_get(f"sensor.10_10_10_10_{sensor_name}")
    assert entry == snapshot(exclude=props("unique_id"))

    state = hass.states.get(f"sensor.10_10_10_10_{sensor_name}")
    assert state == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_packet_loss_when_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Report measured packet loss while round-trip times are unavailable."""
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host("10.10.10.10", 5, []),
    ):
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.10_10_10_10_packet_loss")) is not None
    assert state.state == "100.0"
    assert (state := hass.states.get("binary_sensor.10_10_10_10")) is not None
    assert state.state == STATE_OFF
    assert (
        state := hass.states.get("sensor.10_10_10_10_round_trip_time_average")
    ) is not None
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get("sensor.10_10_10_10_jitter")) is not None
    assert state.state == STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host("10.10.10.10", 5, [1, 2, 3, 4]),
    ):
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.10_10_10_10_packet_loss")) is not None
    assert state.state == "20.0"
    assert (
        state := hass.states.get("sensor.10_10_10_10_round_trip_time_average")
    ) is not None
    assert state.state == "2.5"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_packet_loss_initially_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Create the packet loss sensor when the first sweep receives no replies."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host("10.10.10.10", 5, []),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.10_10_10_10_packet_loss")) is not None
    assert state.state == "100.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "initial_result",
    [
        pytest.param(Host("10.10.10.10", 5, []), id="unreachable"),
        pytest.param(NameLookupError("example.com"), id="dns_failure"),
        pytest.param(Host("10.10.10.10", 0, []), id="no_packets_sent"),
    ],
)
async def test_sensors_recover_after_initial_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    initial_result: Host | NameLookupError,
) -> None:
    """Create all supported sensors even if the first measurement fails."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        side_effect=[initial_result, Host("10.10.10.10", 5, [1, 2, 3, 4])],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all("sensor")) == 5
        assert (
            state := hass.states.get("sensor.10_10_10_10_round_trip_time_average")
        ) is not None
        assert state.state == STATE_UNAVAILABLE
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert {
        state.entity_id: state.state for state in hass.states.async_all("sensor")
    } == {
        "sensor.10_10_10_10_round_trip_time_average": "2.5",
        "sensor.10_10_10_10_round_trip_time_maximum": "4",
        "sensor.10_10_10_10_round_trip_time_minimum": "1",
        "sensor.10_10_10_10_jitter": "1.0",
        "sensor.10_10_10_10_packet_loss": "20.0",
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NameLookupError("example.com"), id="dns_failure"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_packet_loss_unavailable_on_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, error: Exception
) -> None:
    """Do not expose stale packet loss when a new measurement cannot be made."""
    with patch("homeassistant.components.ping.helpers.async_ping", side_effect=error):
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.10_10_10_10_packet_loss")) is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_packet_loss_unavailable_without_sent_packets(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not report zero packet loss when no packets could be sent."""
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host("10.10.10.10", 0, []),
    ):
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.10_10_10_10_packet_loss")) is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("ping_output", "expected_states"),
    [
        pytest.param(
            b"rtt min/avg/max/mdev = 1.000/2.000/3.000/0.100 ms\n",
            {
                "sensor.10_10_10_10_round_trip_time_average": "2.000",
                "sensor.10_10_10_10_round_trip_time_maximum": "3.000",
                "sensor.10_10_10_10_round_trip_time_minimum": "1.000",
                "sensor.10_10_10_10_round_trip_time_mean_deviation": "0.100",
            },
            id="iputils",
        ),
        pytest.param(
            b"round-trip min/avg/max = 1.000/2.000/3.000 ms\n",
            {
                "sensor.10_10_10_10_round_trip_time_average": "2.000",
                "sensor.10_10_10_10_round_trip_time_maximum": "3.000",
                "sensor.10_10_10_10_round_trip_time_minimum": "1.000",
            },
            id="busybox",
        ),
    ],
)
async def test_subprocess_sensors_recover_after_initial_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ping_output: bytes,
    expected_states: dict[str, str],
) -> None:
    """Discover only the sensors supported by the ping binary after recovery."""
    failed_ping = Mock(
        returncode=1,
        communicate=AsyncMock(
            return_value=(b"5 packets transmitted, 0 received, 100% packet loss\n", b"")
        ),
    )
    successful_ping = Mock(
        returncode=0, communicate=AsyncMock(return_value=(ping_output, b""))
    )
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.ping._can_use_icmp_lib_with_privilege",
            return_value=None,
        ),
        patch(
            "asyncio.create_subprocess_exec",
            side_effect=[failed_ping, successful_ping, successful_ping],
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        await config_entry.runtime_data.async_refresh()
        await hass.async_block_till_done()

    assert {
        state.entity_id: state.state for state in hass.states.async_all("sensor")
    } == expected_states
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
