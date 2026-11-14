"""Tests for the Bbox integration setup."""

from unittest.mock import MagicMock

from bbox_api import (
    BboxApiError,
    BboxConnectionError,
    BboxInvalidCredentialsError,
    BboxRateLimitError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bbox.const import DOMAIN
from homeassistant.components.bbox.coordinator import BboxCoordinator
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DEVICE, HOST, HOSTS, PASSWORD, STATS


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry sets up the coordinator and forwards the platforms."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator: BboxCoordinator = mock_config_entry.runtime_data
    assert coordinator.data.device is DEVICE
    assert coordinator.data.stats is STATS
    assert coordinator.data.hosts == HOSTS

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    # The client is closed on unload so reloads do not leak sessions.
    mock_bbox_client.return_value.close.assert_awaited_once()


async def test_setup_without_password_triggers_reauth(hass: HomeAssistant) -> None:
    """Test an imported entry without password asks for reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HOST,
        data={CONF_HOST: HOST, CONF_PASSWORD: "", CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_cannot_connect(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unreachable box puts the entry in SETUP_RETRY."""
    mock_bbox_client.return_value.get_device.side_effect = BboxConnectionError("down")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_invalid_credentials(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test wrong credentials put the entry in SETUP_ERROR (reauth)."""
    mock_bbox_client.return_value.get_hosts.side_effect = BboxInvalidCredentialsError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_rate_limited(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a 429 from the box is a plain retry later, not an auth failure."""
    mock_bbox_client.return_value.get_device.side_effect = BboxRateLimitError()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_bbox_client")
async def test_imported_entry_forwards_sensors_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a YAML import entry creates sensors but no tracker entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        unique_id=HOST,
        title=HOST,
        data={
            CONF_HOST: HOST,
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: True,
            CONF_MONITORED_VARIABLES: ["uptime"],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.bbox_uptime") is not None
    platforms = {
        registry_entry.domain
        for registry_entry in entity_registry.entities.values()
        if registry_entry.config_entry_id == entry.entry_id
    }
    # While the legacy YAML scanner exists, imported entries must not
    # register replacement trackers: they would claim suffixed entity ids.
    assert platforms == {Platform.SENSOR}


async def test_setup_api_error(
    hass: HomeAssistant,
    mock_bbox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a generic API error is retried, not treated as authentication."""
    mock_bbox_client.return_value.get_device.side_effect = BboxApiError("bad payload")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
