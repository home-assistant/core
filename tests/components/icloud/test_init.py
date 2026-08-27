"""Tests for the iCloud config flow."""

from unittest.mock import Mock, patch

from pyicloud.exceptions import PyiCloudFailedLoginException
import pytest

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


@pytest.mark.usefixtures("service_2fa")
async def test_setup_2fa(hass: HomeAssistant) -> None:
    """Test that 2FA login triggers reauth flow."""
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
    assert config_entry.runtime_data.api is not None


@pytest.mark.usefixtures("service_2fa_failed")
async def test_setup_password_failed(hass: HomeAssistant) -> None:
    """Test that invalid login triggers reauth flow."""
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
