"""The tests for the Ring component."""

from datetime import timedelta
from unittest.mock import patch

import pytest
import requests_mock
from ring_doorbell import AuthenticationError, RingError, RingTimeout

import homeassistant.components.ring as ring
from homeassistant.components.ring import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def test_setup(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test the setup."""
    await async_setup_component(hass, ring.DOMAIN, {})

    requests_mock.post(
        "https://oauth.ring.com/oauth/token", text=load_fixture("oauth.json", "ring")
    )
    requests_mock.post(
        "https://api.ring.com/clients_api/session",
        text=load_fixture("session.json", "ring"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("devices.json", "ring"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/chimes/999999/health",
        text=load_fixture("chime_health_attrs.json", "ring"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/doorbots/987652/health",
        text=load_fixture("doorboot_health_attrs.json", "ring"),
    )


async def test_auth_failed_on_setup(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auth failure on setup entry."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "ring_doorbell.Ring.update_data",
        side_effect=AuthenticationError,
    ):
        assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_auth_failure_on_global_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test authentication failure on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    with patch(
        "ring_doorbell.Ring.update_devices",
        side_effect=AuthenticationError,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert "Ring access token is no longer valid, need to re-authenticate" in [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]

        assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_auth_failure_on_device_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test authentication failure on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    with patch(
        "ring_doorbell.RingDoorBell.history",
        side_effect=AuthenticationError,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert "Ring access token is no longer valid, need to re-authenticate" in [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]

        assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Time out fetching Ring device data",
        ),
        (
            RingError,
            "Error fetching Ring device data: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_global_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
    error_type,
    log_msg,
) -> None:
    """Test error on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "ring_doorbell.Ring.update_devices",
        side_effect=error_type,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert log_msg in [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]

        assert mock_config_entry.entry_id in hass.data[DOMAIN]


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Time out fetching Ring history data for device aacdef123",
        ),
        (
            RingError,
            "Error fetching Ring history data for device aacdef123: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_device_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
    error_type,
    log_msg,
) -> None:
    """Test auth failure on data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "ring_doorbell.RingDoorBell.history",
        side_effect=error_type,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert log_msg in [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]
        assert mock_config_entry.entry_id in hass.data[DOMAIN]
