"""Tests for the pyLoad Sensors."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pyload.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.pyload.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test setup of the pyload sensor platform."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "exception",
    [CannotConnect, InvalidAuth, ParserError],
)
async def test_sensor_update_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test if pyLoad sensors go unavailable when exceptions occur (except ParserErrors)."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyloadapi.get_status.side_effect = exception
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_invalid_auth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test invalid auth during sensor update."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyloadapi.get_status.side_effect = InvalidAuth
    mock_pyloadapi.login.side_effect = InvalidAuth

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        "Authentication failed for username, verify your login credentials"
        in caplog.text
    )


async def test_pyload_pre_0_5_0(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test setup of the pyload sensor platform."""
    mock_pyloadapi.get_status.return_value = {
        "pause": False,
        "active": 1,
        "queue": 6,
        "total": 37,
        "speed": 5405963.0,
        "download": True,
        "reconnect": False,
    }
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
