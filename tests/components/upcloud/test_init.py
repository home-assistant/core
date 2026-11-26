"""Tests for the UpCloud integration setup."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests.exceptions
from upcloud_api import UpCloudAPIError

from homeassistant.components.upcloud.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant


async def test_setup_authentication_failed(hass: HomeAssistant) -> None:
    """Test setup starts a reauth flow when authentication fails."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )
    entry.add_to_hass(hass)

    with patch(
        "upcloud_api.CloudManager.authenticate",
        side_effect=UpCloudAPIError(
            error_code="AUTHENTICATION_FAILED",
            error_message="Authentication failed using the given username and password.",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Authentication with UpCloud failed"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    ("exc", "state"),
    [
        pytest.param(
            UpCloudAPIError(
                error_code="ACCOUNT_LOCKED", error_message="The account is locked."
            ),
            ConfigEntryState.SETUP_ERROR,
            id="api_error",
        ),
        pytest.param(
            requests.exceptions.ConnectionError(),
            ConfigEntryState.SETUP_RETRY,
            id="cannot_connect",
        ),
    ],
)
async def test_setup_other_errors(
    hass: HomeAssistant, exc: Exception, state: ConfigEntryState
) -> None:
    """Test other setup errors do not start a reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )
    entry.add_to_hass(hass)

    with patch("upcloud_api.CloudManager.authenticate", side_effect=exc):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is state
    assert not hass.config_entries.flow.async_progress()


async def test_update_authentication_failed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test an authentication error during an update starts a reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
    )
    entry.add_to_hass(hass)

    with (
        patch("upcloud_api.CloudManager.authenticate"),
        patch("upcloud_api.CloudManager.get_servers", return_value=[]) as mock_get,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        # Without servers there are no entities, and without a listener the
        # coordinator does not poll.
        entry.runtime_data.async_add_listener(lambda: None)

        mock_get.side_effect = UpCloudAPIError(
            error_code="AUTHENTICATION_FAILED",
            error_message="Authentication failed using the given username and password.",
        )
        freezer.tick(DEFAULT_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
