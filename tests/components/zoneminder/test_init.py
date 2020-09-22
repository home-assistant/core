"""Tests for init functions."""

import pytest
from zoneminder.zm import ZoneMinder

from homeassistant import config_entries
from homeassistant.components.zoneminder import async_setup_entry
from homeassistant.components.zoneminder.const import (
    CONF_PATH_ZMS,
    DOMAIN,
    SERVICE_SET_RUN_STATE,
)
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_config_not_ready(zoneminder_mock, hass: HomeAssistant) -> None:
    """Test config entry not ready is thrown."""
    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = False
    zm_client.get_monitors.return_value = []
    zm_client.is_available.return_value = True

    zoneminder_mock.return_value = zm_client

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_USER,
        data={
            CONF_HOST: "host1",
            CONF_USERNAME: "username1",
            CONF_PASSWORD: "password1",
            CONF_PATH: "path1",
            CONF_PATH_ZMS: "path_zms1",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
    )
    config_entry.add_to_hass(hass)
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_load_call_service_and_unload(
    zoneminder_mock, hass: HomeAssistant
) -> None:
    """Test config entry load/unload and calling of service."""
    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = []
    zm_client.is_available.return_value = True

    zoneminder_mock.return_value = zm_client

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_USER,
        data={
            CONF_HOST: "host1",
            CONF_USERNAME: "username1",
            CONF_PASSWORD: "password1",
            CONF_PATH: "path1",
            CONF_PATH_ZMS: "path_zms1",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        unique_id="host1",
    )
    config_entry.add_to_hass(hass)
    await async_setup_entry(hass, config_entry)

    assert hass.services.has_service(DOMAIN, SERVICE_SET_RUN_STATE)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RUN_STATE,
        {ATTR_ID: "host1", ATTR_NAME: "away"},
    )
    await hass.async_block_till_done()
    zm_client.set_active_state.assert_called_with("away")

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_RUN_STATE)
