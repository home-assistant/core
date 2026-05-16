"""Tests for the luci device tracker."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.luci.config_flow import InvalidAuth
from homeassistant.components.luci.const import DOMAIN
from homeassistant.components.luci.device_tracker import async_setup_scanner
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .conftest import MOCK_DEVICE_2

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SCANNER_CONFIG = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
}


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_luci_client")
async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device tracker entities are created."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device goes not_home when disconnected."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_HOME

    # Simulate device disconnecting
    mock_luci_client.get_all_connected_devices.return_value = [MOCK_DEVICE_2]

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{DEVICE_TRACKER_DOMAIN}.device1")
    assert state is not None
    assert state.state == STATE_NOT_HOME


async def test_async_setup_scanner_invalid_auth(hass: HomeAssistant) -> None:
    """Test async_setup_scanner creates an issue on invalid auth."""
    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=InvalidAuth,
    ):
        result = await async_setup_scanner(hass, SCANNER_CONFIG, AsyncMock())

    assert result is True
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_invalid_auth")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}


async def test_async_setup_scanner_cannot_connect(hass: HomeAssistant) -> None:
    """Test async_setup_scanner creates an issue on connection failure."""
    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=ConnectionError,
    ):
        result = await async_setup_scanner(hass, SCANNER_CONFIG, AsyncMock())

    assert result is True
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}
