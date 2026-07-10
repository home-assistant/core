"""Test the NeoPool integration setup, unload, and lifecycle."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus.registers import MAX_RELAY_GPIO
import pytest

from homeassistant.components.neopool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import setup_integration
from .conftest import MOCK_POOL_DATA, MOCK_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_neopool_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up the integration end-to-end and tear it down again."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_first_refresh_fails_marks_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Setup re-tries when the first Modbus read raises."""
    mock_neopool_client.async_read_all = AsyncMock(
        side_effect=ConnectionError("Modbus down")
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_neopool_client")
async def test_device_registered_with_firmware(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The first successful read populates firmware on the device entry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_SERIAL)})
    assert device is not None
    assert "18.52" in (device.sw_version or "")


async def test_transient_modbus_failure_after_first_success_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entities transition to unavailable when polling fails after a good read."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "sensor.neopool_water_temperature"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    mock_neopool_client.async_read_all.side_effect = ConnectionError("Modbus fail")
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_corrupt_gpio_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A GPIO register outside 0..MAX_RELAY_GPIO opens a corrupted_gpio issue."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)

    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR


@pytest.mark.usefixtures("mock_neopool_client")
async def test_clean_gpio_does_not_create_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A clean read does not open a corrupted_gpio issue."""
    await setup_integration(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


@pytest.mark.usefixtures("mock_neopool_client")
async def test_corrupt_gpio_clears_stale_issue_from_previous_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A stale issue from a previous session clears on the first clean poll."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "corrupted_gpio",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="corrupted_gpio",
        translation_placeholders={"details": "- stale"},
    )
    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is not None

    await setup_integration(hass, mock_config_entry)

    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


async def test_corrupt_gpio_logs_error_only_on_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ERROR log fires on entering corruption and clears on healing."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)

    await setup_integration(hass, mock_config_entry)
    assert sum("Corrupted GPIO register" in r.message for r in caplog.records) == 1

    caplog.clear()
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not any("Corrupted GPIO register" in r.message for r in caplog.records)

    mock_neopool_client.async_read_all = AsyncMock(return_value=dict(MOCK_POOL_DATA))
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


async def test_corrupt_gpio_updates_issue_on_value_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The repair issue details refresh when a corrupted register value changes."""
    first = dict(MOCK_POOL_DATA)
    first["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=first)

    await setup_integration(hass, mock_config_entry)
    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert str(MAX_RELAY_GPIO + 1) in issue.translation_placeholders["details"]

    second = dict(MOCK_POOL_DATA)
    second["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 2
    mock_neopool_client.async_read_all = AsyncMock(return_value=second)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert str(MAX_RELAY_GPIO + 2) in issue.translation_placeholders["details"]
