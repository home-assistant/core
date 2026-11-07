"""Tests for the TrueNAS sensor platform."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

from aiotruenas import (
    InterfaceTraffic,
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASCallTimeoutError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.truenas_ce.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration
from .const import NETWORK_INTERFACES, SYSTEM_STATS, make_interface


@pytest.mark.usefixtures("mock_truenas_client", "mock_truenas_system")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger the next coordinator update."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_truenas_client")
async def test_new_interface_added(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test traffic sensors are added for new interfaces and links that come up."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.truenas_eno1_rx") is not None
    assert hass.states.get("sensor.truenas_eno2_rx") is None
    assert hass.states.get("sensor.truenas_eno3_rx") is None

    mock_truenas_system.get_network_interfaces.return_value = {
        **NETWORK_INTERFACES,
        "eno2": make_interface("eno2", link_up=True),
        "eno3": make_interface("eno3", link_up=True),
    }
    mock_truenas_system.get_system_stats.return_value = replace(
        SYSTEM_STATS,
        interfaces={
            **SYSTEM_STATS.interfaces,
            "eno3": InterfaceTraffic(rx_kbps=8.0, tx_kbps=16.0),
        },
    )
    await _async_poll(hass, freezer)

    assert (state := hass.states.get("sensor.truenas_eno2_rx"))
    assert state.state == "0.0"
    assert (state := hass.states.get("sensor.truenas_eno3_tx"))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_truenas_client")
async def test_removed_interface_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test traffic sensors of a removed interface become unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_truenas_system.get_network_interfaces.return_value = {
        "eno2": NETWORK_INTERFACES["eno2"]
    }
    await _async_poll(hass, freezer)

    assert (state := hass.states.get("sensor.truenas_eno1_rx"))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get("sensor.truenas_uptime"))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_truenas_client")
async def test_no_traffic_reading(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an interface without a traffic reading has an unknown state."""
    await setup_integration(hass, mock_config_entry)

    mock_truenas_system.get_system_stats.return_value = replace(
        SYSTEM_STATS, interfaces={}
    )
    await _async_poll(hass, freezer)

    assert (state := hass.states.get("sensor.truenas_eno1_rx"))
    assert state.state == "unknown"


@pytest.mark.usefixtures("mock_truenas_client")
async def test_no_cpu_temperature(
    hass: HomeAssistant,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no temperature sensor is created without a temperature reading."""
    mock_truenas_system.get_system_stats.return_value = replace(
        SYSTEM_STATS, cpu_temperature=None
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.truenas_cpu_usage") is not None
    assert hass.states.get("sensor.truenas_temperature") is None


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (TrueNASCallTimeoutError("timed out"), UpdateFailed),
        (TrueNASCallError("failed", errname="EFAULT"), UpdateFailed),
        (TrueNASAuthenticationError("rejected"), ConfigEntryError),
        (TrueNASCallError("denied", errname="EACCES"), ConfigEntryError),
    ],
)
async def test_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_truenas_client: MagicMock,
    mock_truenas_system: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected: type[Exception],
) -> None:
    """Test the sensors become unavailable on a failed update and recover."""
    await setup_integration(hass, mock_config_entry)

    mock_truenas_system.get_system_info.side_effect = exception
    await _async_poll(hass, freezer)

    assert (state := hass.states.get("sensor.truenas_uptime"))
    assert state.state == STATE_UNAVAILABLE
    assert isinstance(mock_config_entry.runtime_data.last_exception, expected)

    mock_truenas_system.get_system_info.side_effect = None
    await _async_poll(hass, freezer)

    assert (state := hass.states.get("sensor.truenas_uptime"))
    assert state.state != STATE_UNAVAILABLE
    # Every poll (re)connects first, which recovers a dropped connection.
    assert mock_truenas_client.return_value.connect.await_count == 3
