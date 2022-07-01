"""Tests for the AdGuard Home switch platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.adguard.const import (
    DOMAIN,
    SERVICE_ADD_URL,
    SERVICE_DISABLE_URL,
    SERVICE_ENABLE_URL,
    SERVICE_REFRESH,
    SERVICE_REMOVE_URL,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant

from .const import FIXTURE_USER_INPUT

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "bypass_version", "bypass_switch_state_update", "disable_sensors"
)
async def test_services(hass: HomeAssistant):
    """Test service calls."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, entry_id="test"
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("adguardhome.filtering.AdGuardHomeFiltering.add_url") as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_URL,
            {
                ATTR_ENTITY_ID: "switch.adguard_safe_browsing",
                CONF_NAME: "test",
                CONF_URL: "http://test.com",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock.assert_awaited_once()

    with patch("adguardhome.filtering.AdGuardHomeFiltering.remove_url") as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_URL,
            {
                ATTR_ENTITY_ID: "switch.adguard_safe_browsing",
                CONF_URL: "http://test.com",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock.assert_awaited_once()

    with patch("adguardhome.filtering.AdGuardHomeFiltering.enable_url") as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENABLE_URL,
            {
                ATTR_ENTITY_ID: "switch.adguard_safe_browsing",
                CONF_URL: "http://test.com",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock.assert_awaited_once()

    with patch("adguardhome.filtering.AdGuardHomeFiltering.disable_url") as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DISABLE_URL,
            {
                ATTR_ENTITY_ID: "switch.adguard_safe_browsing",
                CONF_URL: "http://test.com",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock.assert_awaited_once()

    with patch("adguardhome.filtering.AdGuardHomeFiltering.refresh") as mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            {
                ATTR_ENTITY_ID: "switch.adguard_safe_browsing",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock.assert_awaited_once()
