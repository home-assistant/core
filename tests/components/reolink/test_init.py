"""Test the Reolink init."""
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

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
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("reolink_connect", "reolink_init")


@pytest.fixture(name="config_entry")
def reolink_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
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


@pytest.mark.parametrize(
    ("attr", "value", "expected"),
    [
        (
            "is_admin",
            False,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "get_host_data",
            AsyncMock(side_effect=ValueError("Test error")),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            "get_states",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "supported",
            Mock(return_value=False),
            ConfigEntryState.LOADED,
        ),
        (
            "check_new_firmware",
            AsyncMock(side_effect=ReolinkError("Test error")),
            ConfigEntryState.LOADED,
        ),
    ],
)
async def test_failures_parametrized(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
    attr: str,
    value: Any,
    expected: ConfigEntryState,
) -> None:
    """Test outcomes when changing errors."""
    setattr(reolink_connect, attr, value)
    assert await hass.config_entries.async_setup(config_entry.entry_id) is (
        expected == ConfigEntryState.LOADED
    )
    await hass.async_block_till_done()

    assert config_entry.state == expected
    if expected != ConfigEntryState.LOADED:
        assert not hass.data.get(const.DOMAIN)


async def test_update_listener(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the update listener."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.title == "test_reolink_name"

    hass.config_entries.async_update_entry(config_entry, title="New Name")
    await hass.async_block_till_done()

    assert config_entry.title == "New Name"


async def test_http_no_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test no repairs issue is raised when http local url is used."""
    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") not in issue_registry.issues


async def test_https_repair_issue(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test repairs issue is raised when https local url is used."""
    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "https://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") in issue_registry.issues
