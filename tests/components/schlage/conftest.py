"""Common fixtures for the Schlage tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, create_autospec, patch

from pyschlage.lock import Lock
import pytest

from homeassistant.components.schlage.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title="asdf@asdf.com",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "asdf@asdf.com",
            CONF_PASSWORD: "hunter2",
        },
        unique_id="abc123",
    )


@pytest.fixture
async def mock_added_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyschlage_auth: Mock,
    mock_schlage: Mock,
    mock_lock: Mock,
) -> MockConfigEntry:
    """Mock ConfigEntry that's been added to HA."""
    mock_schlage.locks.return_value = [mock_lock]
    mock_schlage.users.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.config_entries.async_domains()
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.schlage.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_schlage() -> Mock:
    """Mock pyschlage.Schlage."""
    with patch("pyschlage.Schlage", autospec=True) as mock_schlage:
        yield mock_schlage.return_value


@pytest.fixture
def mock_pyschlage_auth() -> Mock:
    """Mock pyschlage.Auth."""
    with patch("pyschlage.Auth", autospec=True) as mock_auth:
        mock_auth.return_value.user_id = "abc123"
        yield mock_auth.return_value


@pytest.fixture
def mock_lock() -> Mock:
    """Mock Lock fixture."""
    mock_lock = create_autospec(Lock)
    mock_lock.configure_mock(
        device_id="test",
        name="Vault Door",
        model_name="<model-name>",
        is_locked=False,
        is_jammed=False,
        battery_level=20,
        firmware_version="1.0",
        lock_and_leave_enabled=True,
        beeper_enabled=True,
    )
    mock_lock.logs.return_value = []
    mock_lock.last_changed_by.return_value = "thumbturn"
    mock_lock.keypad_disabled.return_value = False
    return mock_lock
