"""Utilities for Risco tests."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.components.risco.const import DOMAIN, TYPE_LOCAL
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

TEST_CLOUD_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "1234",
}
TEST_LOCAL_CONFIG = {
    CONF_TYPE: TYPE_LOCAL,
    CONF_HOST: "test-host",
    CONF_PORT: 5004,
    CONF_PIN: "1234",
}
TEST_SITE_UUID = "test-site-uuid"
TEST_SITE_NAME = "test-site-name"


async def setup_risco_cloud(hass, events=[], options={}):
    """Set up a Risco integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_CLOUD_CONFIG, options=options
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.risco.RiscoCloud.login",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoCloud.site_uuid",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.site_name",
        new_callable=PropertyMock(return_value=TEST_SITE_NAME),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.close"
    ), patch(
        "homeassistant.components.risco.RiscoCloud.get_events",
        return_value=events,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_risco_local(hass, options={}):
    """Set up a Risco integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=TEST_LOCAL_CONFIG, options=options
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.risco.RiscoLocal.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoLocal.id",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.disconnect"
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def zone_mock():
    """Return a mocked zone."""
    return MagicMock(
        triggered=False, bypassed=False, bypass=AsyncMock(return_value=True)
    )
