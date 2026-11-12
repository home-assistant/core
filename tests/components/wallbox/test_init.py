"""Test Wallbox Init Component."""

from datetime import timedelta
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.number import NumberService, NumberServiceArgument
from homeassistant.components.wallbox.const import CHARGER_JWT_TTL, CONF_STATION, DOMAIN
from homeassistant.components.wallbox.coordinator import (
    InsufficientRights,
    check_token_validity,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import http_403_error, http_429_error, setup_integration
from .const import (
    MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
    WALLBOX_STATUS_RESPONSE_NO_POWER_BOOST,
)


@pytest.mark.parametrize(
    ("remaining_seconds", "valid"),
    [(-1, False), (0, False), (1, True)],
)
def test_token_validity(remaining_seconds: int, valid: bool) -> None:
    """Check the token validity boundary after accounting for clock drift."""
    now = 1_700_000_000
    drift = 30
    with patch(
        "homeassistant.components.wallbox.coordinator.time.time", return_value=now
    ):
        assert (
            check_token_validity((now + drift + remaining_seconds) * 1000, drift)
            is valid
        )


async def test_wallbox_setup_unload_entry(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error_too_many_requests(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with connection error."""

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_429_error):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.SETUP_RETRY

        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_error_auth(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_wallbox,
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    data = dict(entry.data)
    data[CHARGER_JWT_TTL] = (time.time() - 3600) * 1000
    hass.config_entries.async_update_entry(entry, data=data)

    with (
        patch.object(mock_wallbox, "authenticate", side_effect=http_403_error),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await hass.services.async_call(
            "number",
            NumberService.SET_VALUE,
            {
                CommonServiceArgument.ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                NumberServiceArgument.VALUE: 1.1,
            },
            blocking=True,
        )

    with (
        patch.object(mock_wallbox, "authenticate", side_effect=http_429_error),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "number",
            NumberService.SET_VALUE,
            {
                CommonServiceArgument.ENTITY_ID: MOCK_NUMBER_ENTITY_ENERGY_PRICE_ID,
                NumberServiceArgument.VALUE: 1.1,
            },
            blocking=True,
        )

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_http_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_403_error):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_too_many_requests(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with authentication error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "getChargerStatus", side_effect=http_429_error):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120), True)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_refresh_failed_connection_error(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox setup with connection error."""

    await setup_integration(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(mock_wallbox, "pauseChargingSession", side_effect=http_403_error):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=120), True)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_wallbox_setup_load_entry_no_eco_mode(
    hass: HomeAssistant, entry: MockConfigEntry, mock_wallbox
) -> None:
    """Test Wallbox Unload."""
    with patch.object(
        mock_wallbox,
        "getChargerStatus",
        return_value=WALLBOX_STATUS_RESPONSE_NO_POWER_BOOST,
    ):
        await setup_integration(hass, entry)
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_insufficient_rights_issue_per_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_wallbox: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each entry gets its own linked insufficient rights issue."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**entry.data, CONF_STATION: "67890"},
        entry_id="otherEntry",
    )
    other_entry.add_to_hass(hass)
    await setup_integration(hass, entry)
    assert other_entry.state is ConfigEntryState.LOADED

    mock_wallbox.lockCharger.side_effect = http_403_error
    for config_entry in (entry, other_entry):
        with pytest.raises(InsufficientRights):
            await config_entry.runtime_data.async_set_lock_unlock(True)

    for config_entry in (entry, other_entry):
        issue = issue_registry.async_get_issue(
            DOMAIN, f"insufficient_rights_{config_entry.entry_id}"
        )
        assert issue is not None
        assert issue.config_entry_id == config_entry.entry_id
        assert issue.translation_key == "insufficient_rights"

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, "insufficient_rights_testEntry")
    assert issue_registry.async_get_issue(DOMAIN, "insufficient_rights_otherEntry")


@pytest.mark.parametrize(
    ("api_method", "coordinator_method", "args"),
    [
        pytest.param("lockCharger", "async_set_lock_unlock", (True,), id="lock"),
        pytest.param(
            "setMaxChargingCurrent",
            "async_set_charging_current",
            (16,),
            id="charging_current",
        ),
        pytest.param("setIcpMaxCurrent", "async_set_icp_current", (16,), id="icp"),
        pytest.param("resumeSchedule", "async_resume_schedule", (), id="schedule"),
    ],
)
async def test_insufficient_rights_issue_deleted_on_success(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_wallbox: MagicMock,
    issue_registry: ir.IssueRegistry,
    api_method: str,
    coordinator_method: str,
    args: tuple[Any, ...],
) -> None:
    """Test the insufficient rights issue is deleted once a privileged call works."""
    await setup_integration(hass, entry)
    coordinator = entry.runtime_data
    api_mock = getattr(mock_wallbox, api_method)

    api_mock.side_effect = http_403_error
    with pytest.raises(InsufficientRights):
        await getattr(coordinator, coordinator_method)(*args)
    assert issue_registry.async_get_issue(DOMAIN, "insufficient_rights_testEntry")

    api_mock.side_effect = None
    await getattr(coordinator, coordinator_method)(*args)
    assert not issue_registry.async_get_issue(DOMAIN, "insufficient_rights_testEntry")
