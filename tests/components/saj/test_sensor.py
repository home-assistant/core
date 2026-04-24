"""Test the saj sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pysaj
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.saj import MIN_INTERVAL_SEC
from homeassistant.components.saj.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_ethernet: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    # Mock pysaj sensors
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = "TEST123"
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        # Mock Sensors class with some test sensors
        with patch("pysaj.Sensors") as sensors_cls:
            # Create mock sensor objects
            mock_sensor1 = MagicMock()
            mock_sensor1.name = "Current Power"
            mock_sensor1.key = "current_power"
            mock_sensor1.value = 5000.0
            mock_sensor1.unit = "W"
            mock_sensor1.enabled = True
            mock_sensor1.per_day_basis = False
            mock_sensor1.per_total_basis = False

            mock_sensor2 = MagicMock()
            mock_sensor2.name = "Today Yield"
            mock_sensor2.key = "today_yield"
            mock_sensor2.value = 25.5
            mock_sensor2.unit = "kWh"
            mock_sensor2.enabled = True
            mock_sensor2.per_day_basis = True
            mock_sensor2.per_total_basis = False

            # Sensors is only iterated by HA (read() is mocked); use a list, not a
            # MagicMock __iter__, so iteration follows the normal protocol.
            sensors_cls.return_value = [mock_sensor1, mock_sensor2]

            await setup_integration(hass, mock_config_entry_ethernet)
            await snapshot_platform(
                hass, entity_registry, snapshot, mock_config_entry_ethernet.entry_id
            )


async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry_ethernet: MockConfigEntry,
) -> None:
    """Test sensor update handles failures."""
    with patch("pysaj.SAJ") as saj_cls:
        saj_instance = MagicMock()
        saj_instance.serialnumber = "TEST123"
        # Setup read + initial scheduled poll succeed; next poll fails (unknown state).
        saj_instance.read = AsyncMock(side_effect=[True, True, False])
        saj_cls.return_value = saj_instance

        with patch("pysaj.Sensors") as sensors_cls:
            mock_sensor = MagicMock()
            mock_sensor.name = "current_power"
            mock_sensor.key = "current_power"
            mock_sensor.value = 5000.0
            mock_sensor.unit = "W"
            mock_sensor.enabled = True
            mock_sensor.per_day_basis = False
            mock_sensor.per_total_basis = False

            sensors_cls.return_value = [mock_sensor]

            entry = await setup_integration(hass, mock_config_entry_ethernet)
            assert entry.state is ConfigEntryState.LOADED

            await hass.async_block_till_done()

            state = hass.states.get("sensor.saj_current_power")
            assert state is not None
            assert state.state == "5000.0"
            assert saj_instance.read.await_count == 2

            async_fire_time_changed(
                hass, dt_util.utcnow() + timedelta(seconds=MIN_INTERVAL_SEC + 1)
            )
            await hass.async_block_till_done()

            assert saj_instance.read.await_count == 3
            state = hass.states.get("sensor.saj_current_power")
            assert state is not None
            assert state.state == STATE_UNKNOWN


async def test_yaml_import_creates_deprecated_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """YAML platform triggers import; successful import creates remove-YAML issue."""
    with (
        patch("pysaj.SAJ") as saj_cls,
        patch("pysaj.Sensors"),
    ):
        saj_instance = MagicMock()
        saj_instance.serialnumber = "TEST123"
        saj_instance.read = AsyncMock(return_value=True)
        saj_cls.return_value = saj_instance

        assert await async_setup_component(
            hass,
            "sensor",
            {"sensor": {"platform": DOMAIN, CONF_HOST: "192.168.1.10"}},
        )
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue("homeassistant", "deprecated_yaml")
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_yaml_import_failure_creates_domain_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """YAML import failure creates an integration issue explaining the error."""
    with (
        patch("pysaj.SAJ") as saj_cls,
        patch("pysaj.Sensors"),
    ):
        saj_instance = MagicMock()
        saj_instance.read = AsyncMock(
            side_effect=pysaj.UnexpectedResponseException("bad")
        )
        saj_cls.return_value = saj_instance

        assert await async_setup_component(
            hass,
            "sensor",
            {"sensor": {"platform": DOMAIN, CONF_HOST: "192.168.1.10"}},
        )
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert issue is not None
