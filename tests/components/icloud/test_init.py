"""Tests for the iCloud config flow."""

from unittest.mock import Mock, PropertyMock, patch

from pyicloud.exceptions import (
    PyiCloudAuthRequiredException,
    PyiCloudFailedLoginException,
)
import pytest
from requests import Response

from homeassistant.components.icloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import MOCK_CONFIG, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture(name="service_2fa")
def mock_controller_2fa_service():
    """Mock a successful 2fa service."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.is_trusted_session = False
        yield service_mock


@pytest.fixture(name="service_2fa_failed")
def mock_controller_2fa_service_failed():
    """Mock a failed 2fa service."""
    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService"
        ) as service_mock,
        patch(
            "homeassistant.components.icloud.config_flow.PyiCloudService", service_mock
        ),
    ):
        service_mock.side_effect = PyiCloudFailedLoginException("Invalid login")
        yield service_mock


@pytest.fixture(name="service_auth_required")
def mock_controller_auth_required_service():
    """Mock a service that reports the session needs authenticating again."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_mock.side_effect = PyiCloudAuthRequiredException(
            USERNAME, Mock(spec=Response)
        )
        yield service_mock


@pytest.mark.usefixtures("service_2fa")
async def test_setup_2fa(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test that a 2FA challenge starts reauth and is not reported as a bad password."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.config_entries.flow.async_progress()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id
    assert "2FA authentication required" in caplog.text
    assert "no longer working" not in caplog.text

    # The reauth flow reuses this session to send and validate the code, so it
    # has to survive the challenge.
    assert config_entry.runtime_data.api is not None


@pytest.mark.usefixtures("service_2fa_failed")
async def test_setup_password_failed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that a rejected password is reported as such, not as a 2FA prompt."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.config_entries.flow.async_progress()

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id
    assert "no longer working" in caplog.text
    assert "2FA authentication required" not in caplog.text
    assert config_entry.runtime_data.api is None


@pytest.mark.usefixtures("service_2fa")
async def test_unique_id_set_on_setup(hass: HomeAssistant) -> None:
    """Test that unique_id is set on setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=None
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.unique_id == USERNAME
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("service_auth_required")
async def test_setup_auth_required(hass: HomeAssistant) -> None:
    """Test that an auth-required login failure starts reauth."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id


async def test_auth_required_on_first_fetch_is_retried(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that losing the session before the first fetch is retried.

    The fetch timer is only armed once update_devices() completes, so an entry
    that gives up here would stay loaded and never poll again.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudAuthRequiredException(USERNAME, Mock(spec=Response))
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # SETUP_RETRY, so Home Assistant retries with backoff instead of leaving a
    # loaded entry that never polls.
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_token_on_first_fetch_starts_reauth(
    hass: HomeAssistant, service_2fa: Mock
) -> None:
    """Test that a token rejected on the first fetch asks the user to log in.

    iCloud only rejects a stale stored token when the session is refreshed to
    read the devices, so this surfaces after a successful looking login.
    """
    service_2fa.return_value.requires_2fa = False
    type(service_2fa.return_value).devices = PropertyMock(
        side_effect=PyiCloudFailedLoginException("Invalid authentication token.")
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["context"]["source"] == "reauth"
    ]
