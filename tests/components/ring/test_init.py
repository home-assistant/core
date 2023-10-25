"""The tests for the Ring component."""

from unittest.mock import patch

import pytest
import requests_mock
from ring_doorbell import AuthenticationError, RingError, RingTimeout

from homeassistant import config_entries
import homeassistant.components.ring as ring
from homeassistant.components.ring import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


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


@pytest.mark.parametrize("hastoken", ["hastoken", "notoken"])
async def test_migrate_entry(hass: HomeAssistant, hastoken) -> None:
    """Test migrate entry to version 2."""
    if hastoken == "hastoken":
        data = {"username": "foo", "token": {}}
    else:
        data = {
            "username": "foo",
        }

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=data,
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    assert mock_entry.version == 2
    assert mock_entry.data.get("token") is None
    assert (
        sum(
            1
            for x in mock_entry.async_get_active_flows(
                hass, [config_entries.SOURCE_REAUTH]
            )
        )
        == 1
    )


async def test_no_listen_start(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, caplog
) -> None:
    """Test behaviour if listener doesn't start."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"username": "foo", CONF_ACCESS_TOKEN: {}},
    )

    mock_entry.add_to_hass(hass)
    with patch("ring_doorbell.Ring.start_event_listener", return_value=False):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert "Ring event listener failed to started after 5 seconds" in [
        record.message for record in caplog.records if record.levelname == "ERROR"
    ]
    assert not hass.data[DOMAIN][mock_entry.entry_id]["listener_started_in_time"]


async def test_auth_failed_on_setup(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, caplog
) -> None:
    """Test auth failure on setup entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"username": "foo", CONF_ACCESS_TOKEN: {}},
    )

    mock_entry.add_to_hass(hass)
    with patch(
        "ring_doorbell.Ring.update_data",
        side_effect=AuthenticationError,
    ):
        assert not any(mock_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        assert any(mock_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize("update_type", ["global", "device"])
async def test_auth_failed_on_update(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, update_type
) -> None:
    """Test auth failure on data update."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"username": "foo", CONF_ACCESS_TOKEN: {}},
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    if update_type == "global":
        patch_method = "ring_doorbell.Ring.update_devices"
    else:
        patch_method = "ring_doorbell.RingDoorBell.history"

    with patch(
        patch_method,
        side_effect=AuthenticationError,
    ):
        if update_type == "global":
            await hass.data[DOMAIN][mock_entry.entry_id][
                "device_data"
            ].async_refresh_all()

        else:
            hass.data[DOMAIN][mock_entry.entry_id]["history_data"].refresh_all()
        await hass.async_block_till_done()
        assert any(mock_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


error_testdata = [
    ("global", RingTimeout, "WARNING", "Time out fetching Ring device data"),
    ("global", RingError, "ERROR", "Error fetching Ring device data: "),
    ("device", RingTimeout, "WARNING", "Time out fetching Ring history data"),
    ("device", RingError, "ERROR", "Error fetching Ring history data: "),
]


@pytest.mark.parametrize(
    ("update_type", "error_type", "log_name", "log_msg"),
    error_testdata,
    ids=["global-timeout", "global-error", "device-timeout", "device-error"],
)
async def test_error_on_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    caplog,
    update_type,
    error_type,
    log_name,
    log_msg,
) -> None:
    """Test auth failure on data update."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"username": "foo", CONF_ACCESS_TOKEN: {}},
    )

    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    if update_type == "global":
        patch_method = "ring_doorbell.Ring.update_devices"
    else:
        patch_method = "ring_doorbell.RingDoorBell.history"

    with patch(
        patch_method,
        side_effect=error_type,
    ):
        if update_type == "global":
            await hass.data[DOMAIN][mock_entry.entry_id][
                "device_data"
            ].async_refresh_all()

        else:
            hass.data[DOMAIN][mock_entry.entry_id]["history_data"].refresh_all()
        await hass.async_block_till_done()

        assert log_msg in [
            record.message for record in caplog.records if record.levelname == log_name
        ]
