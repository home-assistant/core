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


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
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


async def test_device_registered_with_firmware(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
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
) -> None:
    """A GPIO register outside 0..MAX_RELAY_GPIO opens a corrupted_gpio issue."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)

    await setup_integration(hass, mock_config_entry)

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR


async def test_clean_gpio_does_not_create_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """A clean read does not open a corrupted_gpio issue."""
    await setup_integration(hass, mock_config_entry)
    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


async def test_corrupt_gpio_logs_error_only_on_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ERROR log fires on entering corruption and clears on healing."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)

    with caplog.at_level("ERROR"):
        await setup_integration(hass, mock_config_entry)
        assert sum("Corrupted GPIO register" in r.message for r in caplog.records) == 1

        caplog.clear()
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert not any("Corrupted GPIO register" in r.message for r in caplog.records)

        mock_neopool_client.async_read_all = AsyncMock(
            return_value=dict(MOCK_POOL_DATA)
        )
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        issue_registry = ir.async_get(hass)
        assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None
