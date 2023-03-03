"""Test the Reolink init."""
from unittest.mock import patch

from homeassistant.components.reolink import const
from homeassistant.components.reolink.config_flow import DEFAULT_PROTOCOL
from homeassistant.config import async_process_ha_core_config
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


async def test_http_no_repair_issue(hass: HomeAssistant) -> None:
    """Test no repairs issue is raised when http local url is used."""
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

    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "http://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") not in issue_registry.issues


async def test_https_repair_issue(hass: HomeAssistant) -> None:
    """Test repairs issue is raised when https local url is used."""
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

    await async_process_ha_core_config(
        hass, {"country": "GB", "internal_url": "https://test_homeassistant_address"}
    )

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "https_webhook") in issue_registry.issues


async def test_no_firmware_repair_issue(hass: HomeAssistant) -> None:
    """Test no firmware issue is raised when firmware is new enough."""
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

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "firmware_update") not in issue_registry.issues


async def test_firmware_repair_issue(hass: HomeAssistant) -> None:
    """Test firmware issue is raised when too old firmware is used."""
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

    host_mock = get_mock_info(sw_required=True)
    with patch("homeassistant.components.reolink.host.Host", return_value=host_mock):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (const.DOMAIN, "firmware_update") in issue_registry.issues
