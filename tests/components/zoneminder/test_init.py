"""Tests for init functions."""
from datetime import timedelta

from zoneminder.zm import ZoneMinder

from homeassistant import config_entries
from homeassistant.components.zoneminder import const
from homeassistant.components.zoneminder.common import is_client_in_data
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SOURCE,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import MagicMock, patch
from tests.common import async_fire_time_changed


async def test_no_yaml_config(hass: HomeAssistant) -> None:
    """Test empty yaml config."""
    with patch(
        "homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder
    ) as zoneminder_mock:
        zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
        zm_client.get_zms_url.return_value = "http://host1/path_zms1"
        zm_client.login.return_value = True
        zm_client.get_monitors.return_value = []

        zoneminder_mock.return_value = zm_client

        hass_config = {const.DOMAIN: []}
        await async_setup_component(hass, const.DOMAIN, hass_config)
        await hass.async_block_till_done()
        assert not hass.services.has_service(const.DOMAIN, const.SERVICE_SET_RUN_STATE)


async def test_yaml_config_import(hass: HomeAssistant) -> None:
    """Test yaml config import."""
    with patch(
        "homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder
    ) as zoneminder_mock:
        zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
        zm_client.get_zms_url.return_value = "http://host1/path_zms1"
        zm_client.login.return_value = True
        zm_client.get_monitors.return_value = []

        zoneminder_mock.return_value = zm_client

        hass_config = {const.DOMAIN: [{CONF_HOST: "host1"}]}
        await async_setup_component(hass, const.DOMAIN, hass_config)
        await hass.async_block_till_done()
        assert hass.services.has_service(const.DOMAIN, const.SERVICE_SET_RUN_STATE)


async def test_load_call_service_and_unload(hass: HomeAssistant) -> None:
    """Test config entry load/unload and calling of service."""
    with patch(
        "homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder
    ) as zoneminder_mock:
        zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
        zm_client.get_zms_url.return_value = "http://host1/path_zms1"
        zm_client.login.side_effect = [True, True, False, True]
        zm_client.get_monitors.return_value = []
        zm_client.is_available.return_value = True

        zoneminder_mock.return_value = zm_client

        await hass.config_entries.flow.async_init(
            const.DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data={
                CONF_HOST: "host1",
                CONF_USERNAME: "username1",
                CONF_PASSWORD: "password1",
                CONF_PATH: "path1",
                const.CONF_PATH_ZMS: "path_zms1",
                CONF_SSL: False,
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

        config_entry = next(iter(hass.config_entries.async_entries(const.DOMAIN)), None)
        assert config_entry

        assert config_entry.state == ENTRY_STATE_SETUP_RETRY
        assert not is_client_in_data(hass, "host1")

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
        await hass.async_block_till_done()
        assert config_entry.state == ENTRY_STATE_LOADED
        assert is_client_in_data(hass, "host1")

        assert hass.services.has_service(const.DOMAIN, const.SERVICE_SET_RUN_STATE)

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_SET_RUN_STATE,
            {ATTR_ID: "host1", ATTR_NAME: "away"},
        )
        await hass.async_block_till_done()
        zm_client.set_active_state.assert_called_with("away")

        await config_entry.async_unload(hass)
        await hass.async_block_till_done()
        assert config_entry.state == ENTRY_STATE_NOT_LOADED
        assert not is_client_in_data(hass, "host1")
        assert not hass.services.has_service(const.DOMAIN, const.SERVICE_SET_RUN_STATE)
