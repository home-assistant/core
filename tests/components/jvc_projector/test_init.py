"""Tests for JVC Projector config entry."""

from unittest.mock import AsyncMock, patch

from jvcprojector import JvcProjectorAuthError, JvcProjectorTimeoutError

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.issue_registry import IssueRegistry

from . import MOCK_MAC

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test initialization."""
    mac = format_mac(MOCK_MAC)
    device = device_registry.async_get_device(identifiers={(DOMAIN, mac)})
    assert device is not None
    assert device.identifiers == {(DOMAIN, mac)}


async def test_unload_config_entry(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test config entry loading and unloading."""
    mock_config_entry = mock_integration
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_device.disconnect.call_count == 1


async def test_disconnect_on_hass_stop(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test device disconnects when Home Assistant stops."""
    assert mock_integration.state is ConfigEntryState.LOADED
    assert mock_device.disconnect.call_count == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert mock_device.disconnect.call_count == 1


async def test_config_entry_connect_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry with connect error."""
    mock_device.connect.side_effect = JvcProjectorTimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry with auth error."""
    mock_device.connect.side_effect = JvcProjectorAuthError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_deprecated_sensor_issue_lifecycle(
    hass: HomeAssistant,
    issue_registry: IssueRegistry,
    entity_registry: er.EntityRegistry,
    mock_integration: MockConfigEntry,
) -> None:
    """Test deprecated sensor cleanup and issue lifecycle."""
    sensor_unique_id = f"{format_mac(MOCK_MAC)}_hdr_processing"
    issue_id = f"deprecated_sensor_{mock_integration.entry_id}_hdr_processing"

    assert (
        entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, sensor_unique_id)
        is None
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    sensor_entry = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        sensor_unique_id,
        config_entry=mock_integration,
        suggested_object_id="jvc_projector_hdr_processing",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    entity_id = sensor_entry.entity_id

    with patch(
        "homeassistant.components.jvc_projector.util.get_automations_and_scripts_using_entity",
        return_value=["- [Test Automation](/config/automation/edit/test_automation)"],
    ):
        await hass.config_entries.async_reload(mock_integration.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "deprecated_sensor_scripts"
    assert entity_registry.async_get(entity_id) is not None

    await hass.config_entries.async_reload(mock_integration.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id) is None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
