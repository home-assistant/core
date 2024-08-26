"""Tests for the pyLoad Sensors."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.pyload.const import DOMAIN
from homeassistant.components.pyload.coordinator import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

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


async def test_platform_setup_triggers_import_flow(
    hass: HomeAssistant,
    pyload_config: ConfigType,
    mock_setup_entry: AsyncMock,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test if an issue is created when attempting setup from yaml config."""

    assert await async_setup_component(hass, SENSOR_DOMAIN, pyload_config)
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (ParserError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_deprecated_yaml_import_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test an issue is created when attempting setup from yaml config and an error happens."""

    mock_pyloadapi.login.side_effect = exception
    await async_setup_component(hass, SENSOR_DOMAIN, pyload_config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"deprecated_yaml_import_issue_{reason}"
    )


async def test_deprecated_yaml(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    pyload_config: ConfigType,
    mock_pyloadapi: AsyncMock,
) -> None:
    """Test an issue is created when we import from yaml config."""

    await async_setup_component(hass, SENSOR_DOMAIN, pyload_config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN, issue_id=f"deprecated_yaml_{DOMAIN}"
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
