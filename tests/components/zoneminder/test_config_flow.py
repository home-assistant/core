"""Config flow tests."""
import requests
from zoneminder.zm import ZoneMinder

from homeassistant import config_entries
from homeassistant.components.zoneminder import ClientAvailabilityResult
from homeassistant.components.zoneminder.const import CONF_PATH_ZMS, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SOURCE,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.async_mock import MagicMock, patch


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
@patch("homeassistant.components.zoneminder.async_setup_entry")
async def test_import(
    async_create_entry_mock, zoneminder_mock, hass: HomeAssistant
) -> None:
    """Test import from configuration yaml."""
    conf_data = {
        CONF_HOST: "host1",
        CONF_USERNAME: "username1",
        CONF_PASSWORD: "password1",
        CONF_PATH: "path1",
        CONF_PATH_ZMS: "path_zms1",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zoneminder_mock.return_value = zm_client

    zm_client.login.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=conf_data,
    )
    assert result
    assert result["type"] == "abort"
    assert result["reason"] == "auth_fail"

    zm_client.login.return_value = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=conf_data,
    )
    assert result
    assert result["type"] == "create_entry"
    assert result["data"] == {
        **conf_data,
        CONF_SOURCE: config_entries.SOURCE_IMPORT,
    }


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_user(zoneminder_mock, hass: HomeAssistant) -> None:
    """Test user initiated creation."""
    conf_data = {
        CONF_HOST: "host1",
        CONF_USERNAME: "username1",
        CONF_PASSWORD: "password1",
        CONF_PATH: "path1",
        CONF_PATH_ZMS: "path_zms1",
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result
    assert result["type"] == "form"

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zoneminder_mock.return_value = zm_client

    zm_client.login.side_effect = requests.exceptions.ConnectionError()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        conf_data,
    )
    assert result
    assert result["type"] == "form"
    assert result["errors"] == {
        "base": ClientAvailabilityResult.ERROR_CONNECTION_ERROR.value
    }

    zm_client.login.side_effect = None
    zm_client.login.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        conf_data,
    )
    assert result
    assert result["type"] == "form"
    assert result["errors"] == {"base": ClientAvailabilityResult.ERROR_AUTH_FAIL.value}

    zm_client.login.return_value = True
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        conf_data,
    )
    assert result
    assert result["type"] == "create_entry"
    assert result["data"] == conf_data
