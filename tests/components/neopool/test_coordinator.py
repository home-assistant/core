"""Tests for the NeoPool coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus.registers import MAX_RELAY_GPIO
import pytest

from homeassistant.components.neopool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration
from .conftest import MOCK_POOL_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_data_populates_firmware(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """The first successful read populates firmware."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.firmware == "18.52"


async def test_transient_modbus_failure_after_first_success_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failure after at least one good read raises UpdateFailed."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is True

    mock_neopool_client.async_read_all.side_effect = ConnectionError("Modbus fail")
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
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
