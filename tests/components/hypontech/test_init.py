"""Test the Hypontech Cloud init."""

from unittest.mock import AsyncMock, patch

from hyponcloud import AuthenticationError, ConnectionError as HyponConnectionError
import pytest

from homeassistant.components.hypontech.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_timeout(hass: HomeAssistant) -> None:
    """Test setup entry with timeout error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hypontech.HyponCloud.connect",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_authentication_error(hass: HomeAssistant) -> None:
    """Test setup entry with authentication error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hypontech.HyponCloud.connect",
        side_effect=AuthenticationError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test setup entry with connection error during data fetch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.hypontech.HyponCloud.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_overview",
            side_effect=HyponConnectionError,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_success(
    hass: HomeAssistant, mock_hyponcloud: AsyncMock
) -> None:
    """Test successful setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant, mock_hyponcloud: AsyncMock) -> None:
    """Test unload entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.fixture
def mock_hyponcloud():
    """Mock HyponCloud."""
    with (
        patch(
            "homeassistant.components.hypontech.HyponCloud.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.hypontech.coordinator.HyponCloud.get_overview",
        ) as mock_get_overview,
    ):
        mock_get_overview.return_value = AsyncMock()
        yield mock_get_overview
