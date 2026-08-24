"""Test the saj sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
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

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_pysaj_saj")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor update handles failures."""
    # Setup read + initial scheduled poll succeed; next poll fails (unknown state).
    mock_pysaj_saj.read = AsyncMock(side_effect=[True, True, False])

    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.LOADED

    await hass.async_block_till_done()

    state = hass.states.get("sensor.saj_current_power")
    assert state is not None
    assert state.state == "5000.0"
    assert mock_pysaj_saj.read.await_count == 2

    freezer.tick(timedelta(seconds=MIN_INTERVAL_SEC + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_pysaj_saj.read.await_count == 3
    state = hass.states.get("sensor.saj_current_power")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_yaml_import_creates_deprecated_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """YAML platform triggers import; successful import creates remove-YAML issue."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": DOMAIN, CONF_HOST: "192.168.1.10"}},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}")
    assert issue is not None
    assert issue.issue_domain == DOMAIN


async def test_yaml_import_failure_creates_domain_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """YAML import failure creates an integration issue explaining the error."""
    mock_pysaj_saj.read.side_effect = pysaj.UnexpectedResponseException("bad")
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
