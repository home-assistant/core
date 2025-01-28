"""Tests for Vanderbilt SPC component."""

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, PropertyMock, patch

import pyspcwebgw
from pyspcwebgw.const import AreaMode, ZoneInput, ZoneType
import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.spc.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

TEST_CONFIG = {"api_url": "http://localhost/", "ws_url": "ws://localhost/"}


@dataclass
class ZoneData:
    """Test zone data."""

    id: str
    name: str
    type: ZoneType
    device_class: str | None = None


ZONE_DEFINITIONS = [
    ZoneData("1", "Entrance", ZoneType.ENTRY_EXIT),
    ZoneData("2", "Living Room", ZoneType.ALARM),
    ZoneData("3", "Smoke Sensor", ZoneType.FIRE),
    ZoneData("4", "Power Supply", ZoneType.TECHNICAL),
]

ALARM_MODE_MAPPING = [
    ("alarm_disarm", AreaMode.UNSET, AlarmControlPanelState.DISARMED),
    ("alarm_arm_home", AreaMode.PART_SET_A, AlarmControlPanelState.ARMED_HOME),
    ("alarm_arm_night", AreaMode.PART_SET_B, AlarmControlPanelState.ARMED_NIGHT),
    ("alarm_arm_away", AreaMode.FULL_SET, AlarmControlPanelState.ARMED_AWAY),
]


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the SPC client."""
    with (
        patch(
            "homeassistant.components.spc.SpcWebGateway", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.spc.config_flow.SpcWebGateway", new=mock_client
        ),
    ):
        client = mock_client.return_value
        # Remove the default return value for async_load_parameters
        client.async_load_parameters = AsyncMock()
        client.change_mode = AsyncMock()
        client.start = AsyncMock()
        client.stop = AsyncMock()

        # Create mock area
        mock_area = AsyncMock(spec=pyspcwebgw.area.Area)
        mock_area.id = "1"
        mock_area.mode = AreaMode.FULL_SET
        mock_area.last_changed_by = "Sven"
        mock_area.name = "House"
        mock_area.verified_alarm = False

        # Create mock zones using ZoneData
        mock_zones = {}
        for zone_data in ZONE_DEFINITIONS:
            zone = AsyncMock(spec=pyspcwebgw.zone.Zone)
            zone.id = zone_data.id
            zone.name = zone_data.name
            type(zone).type = PropertyMock(return_value=zone_data.type)
            type(zone).input = PropertyMock(return_value=ZoneInput.CLOSED)
            mock_zones[zone.id] = zone

        client.zones = mock_zones
        client.areas = {"1": mock_area}
        client.info = {"sn": "111111", "type": "SPC4000", "version": "3.14.1"}
        client.ethernet = {"ip_address": "127.0.0.1"}

        # Save callback for testing state updates
        mock_client.callback = None

        def _get_instance(*args, **kwargs):
            client.async_callback = kwargs.get("async_callback")
            return client

        mock_client.side_effect = _get_instance

        yield mock_client


@pytest.fixture
async def mock_config(hass: HomeAssistant, mock_client: AsyncMock) -> dict[str, Any]:
    """Mock config setup."""
    config = {"spc": TEST_CONFIG}

    # Setup component and create entry
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    return config


@pytest.fixture
def mock_area(mock_client: AsyncMock) -> pyspcwebgw.area.Area:
    """Return the mock area."""
    return mock_client.return_value.areas["1"]


@pytest.fixture
def mock_zone(mock_client: AsyncMock) -> pyspcwebgw.zone.Zone:
    """Return first mock zone."""
    return mock_client.return_value.zones["1"]


@pytest.fixture(params=ALARM_MODE_MAPPING)
def alarm_mode(
    request: pytest.FixtureRequest,
) -> tuple[str, AreaMode, AlarmControlPanelState]:
    """Parametrize alarm modes."""
    return request.param
