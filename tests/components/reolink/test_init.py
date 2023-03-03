"""Test the Reolink init."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.reolink import const
from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac

from .conftest import (
    TEST_HOST,
    TEST_MAC,
    TEST_NVR_NAME,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_USE_HTTPS,
    TEST_USERNAME,
    get_mock_info,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("reolink_connect", "reolink_init")


def reolink_mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the reolink mock config entry to hass."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_PORT: TEST_PORT,
            const.CONF_USE_HTTPS: TEST_USE_HTTPS,
        },
        options={
            const.CONF_PROTOCOL: DEFAULT_PROTOCOL,
        },
        title=TEST_NVR_NAME,
    )
    config_entry.add_to_hass(hass)

    return config_entry


async def test_ConfigEntryAuthFailed(hass: HomeAssistant) -> None:
    """Test a ConfigEntryAuthFailed is raised when credentials are invalid."""
    config_entry = reolink_mock_config_entry(hass)

    mock_info = get_mock_info()
    mock_info.is_admin = False
    mock_info.user_level = "guest"
    with patch("homeassistant.components.reolink.host.Host", return_value=mock_info):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False

    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(const.DOMAIN)


async def test_ConfigEntryNotReady(hass: HomeAssistant) -> None:
    """Test a ConfigEntryNotReady is raised when initial connection fails."""
    config_entry = reolink_mock_config_entry(hass)

    mock_info = get_mock_info(error=ReolinkError("Test error"))
    with patch("homeassistant.components.reolink.host.Host", return_value=mock_info):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False

    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(const.DOMAIN)


async def test_ConfigEntryNotReady_initial_fetch(hass: HomeAssistant) -> None:
    """Test a ConfigEntryNotReady is raised when initial fetch of data fails."""
    config_entry = reolink_mock_config_entry(hass)

    mock_info = get_mock_info()
    mock_info.get_states = AsyncMock(side_effect=ReolinkError("Test error"))
    with patch("homeassistant.components.reolink.host.Host", return_value=mock_info):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False

    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY
    assert not hass.data.get(const.DOMAIN)


async def test_firmware_update_not_supported(hass: HomeAssistant) -> None:
    """Test successful setup if firmware update is not supported."""
    config_entry = reolink_mock_config_entry(hass)

    mock_info = get_mock_info()
    mock_info.supported = Mock(return_value=False)
    with patch("homeassistant.components.reolink.host.Host", return_value=mock_info):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED


async def test_firmware_update_error(hass: HomeAssistant) -> None:
    """Test error during firmware update does not block setup."""
    config_entry = reolink_mock_config_entry(hass)

    mock_info = get_mock_info()
    mock_info.check_new_firmware = AsyncMock(side_effect=ReolinkError("Test error"))
    with patch("homeassistant.components.reolink.host.Host", return_value=mock_info):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED


async def test_unexpected_error(hass: HomeAssistant) -> None:
    """Test a unexpected error during initial connection."""
    config_entry = reolink_mock_config_entry(hass)

    mock_info = get_mock_info(error=ValueError("Test error"))
    with patch("homeassistant.components.reolink.host.Host", return_value=mock_info):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False

    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(const.DOMAIN)


async def test_update_listener(hass: HomeAssistant) -> None:
    """Test the update listener."""
    config_entry = reolink_mock_config_entry(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.title == "test_reolink_name"

    hass.config_entries.async_update_entry(config_entry, title="New Name")
    await hass.async_block_till_done()

    assert config_entry.title == "New Name"


async def test_http_no_repair_issue(hass: HomeAssistant) -> None:
    """Test no repairs issue is raised when http local url is used."""
    config_entry = reolink_mock_config_entry(hass)

    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") not in issue_registry.issues


async def test_https_repair_issue(hass: HomeAssistant) -> None:
    """Test repairs issue is raised when https local url is used."""
    config_entry = reolink_mock_config_entry(hass)

    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "https://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") in issue_registry.issues
