"""Tests for the Rainforest RAVEn sensors."""

from dataclasses import replace
from datetime import timedelta
import logging
from unittest.mock import AsyncMock
from xml.etree.ElementTree import ParseError

from aioraven.data import CurrentSummationDelivered, InstantaneousDemand, PriceCluster
from aioraven.device import RAVEnConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_MAC, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEMAND, NETWORK_INFO, PRICE_CLUSTER, SUMMATION


@pytest.mark.usefixtures("mock_entry")
async def test_sensors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors."""
    assert len(hass.states.async_all()) == 5

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


@pytest.mark.usefixtures("mock_entry")
async def test_device_update_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of a device error during an update."""
    parse_error = ParseError("mismatched tag: line 27, column 2")
    connection_error = RAVEnConnectionError(str(parse_error))
    connection_error.__cause__ = parse_error
    mock_device.get_network_info.side_effect = (connection_error, NETWORK_INFO)

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "RAVEn returned malformed XML: mismatched tag" in caplog.text

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state == STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)


@pytest.mark.usefixtures("mock_entry")
async def test_device_update_timeout(
    hass: HomeAssistant, mock_device: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test handling of a device timeout during an update."""
    mock_device.get_network_info.side_effect = (TimeoutError, NETWORK_INFO)

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state == STATE_UNAVAILABLE for state in states)

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)


@pytest.mark.usefixtures("mock_entry")
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(OSError("device disconnected"), id="serial-disconnect"),
        pytest.param(RuntimeError("unexpected client error"), id="unexpected-error"),
        pytest.param(None, id="no-network-response"),
    ],
)
async def test_device_update_failure_reconnects(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    freezer: FrozenDateTimeFactory,
    failure: Exception | None,
) -> None:
    """Test reconnecting after an update failure."""
    mock_device.get_network_info.side_effect = (
        failure,
        NETWORK_INFO,
    )

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state == STATE_UNAVAILABLE for state in states)
    assert mock_device.close.call_count == 1

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    states = hass.states.async_all()
    assert len(states) == 5
    assert all(state.state != STATE_UNAVAILABLE for state in states)
    assert mock_device.open.call_count == 2


@pytest.mark.usefixtures("mock_entry")
async def test_device_cache(
    hass: HomeAssistant, mock_device: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test that the device isn't re-opened for subsequent refreshes."""
    assert mock_device.get_network_info.call_count == 1
    assert mock_device.open.call_count == 1

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_device.get_network_info.call_count == 2
    assert mock_device.open.call_count == 1


@pytest.mark.parametrize(
    ("method", "data_type", "response"),
    [
        pytest.param(
            "get_current_summation_delivered",
            "CurrentSummationDelivered",
            replace(SUMMATION, meter_mac_id=bytes.fromhex("0000000000000001")),
            id="summation",
        ),
        pytest.param(
            "get_instantaneous_demand",
            "InstantaneousDemand",
            replace(DEMAND, meter_mac_id=bytes.fromhex("0000000000000001")),
            id="demand",
        ),
        pytest.param(
            "get_current_price",
            "PriceCluster",
            replace(PRICE_CLUSTER, meter_mac_id=bytes.fromhex("0000000000000001")),
            id="price",
        ),
    ],
)
@pytest.mark.usefixtures("mock_entry")
async def test_mismatched_meter_mac_logged(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_device: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    method: str,
    data_type: str,
    response: CurrentSummationDelivered | InstantaneousDemand | PriceCluster,
) -> None:
    """Test a mismatched meter MAC is logged and ignored."""
    caplog.set_level(logging.DEBUG)
    getattr(mock_device, method).return_value = response

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    requested_mac = bytes.fromhex(mock_entry.data[CONF_MAC][0]).hex()
    assert (
        f"Ignoring {data_type} response for meter MAC "
        f"{response.meter_mac_id.hex()} while requesting {requested_mac}"
    ) in caplog.text
    assert repr(response) in caplog.text
    assert f"RAVEn network info response: {NETWORK_INFO!r}" in caplog.text
