"""Test SkyBell config flow."""
from unittest.mock import patch

from requests.exceptions import ConnectTimeout, HTTPError
from skybellpy import exceptions

from homeassistant.components.skybell.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import CONF_CONFIG_FLOW, _patch_skybell

from tests.common import MockConfigEntry


def _patch_setup():
    return patch(
        "homeassistant.components.skybell.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass: HomeAssistant):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with _patch_skybell():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user"
        assert result["data"] == CONF_CONFIG_FLOW


async def test_flow_user_already_configured(hass: HomeAssistant):
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
    )

    entry.add_to_hass(hass)

    service_info = CONF_CONFIG_FLOW
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=service_info
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    with _patch_skybell() as skybellmock:
        skybellmock.side_effect = (ConnectTimeout, HTTPError)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_credentials(hass: HomeAssistant):
    """Test that invalid credentials throws an error."""
    with _patch_skybell() as skybellmock:
        skybellmock.side_effect = exceptions.SkybellAuthenticationException
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_unknown_error(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    with _patch_skybell() as skybellmock:
        skybellmock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}


async def test_flow_import(hass: HomeAssistant):
    """Test import step."""
    with _patch_skybell(), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user"
        assert result["data"] == CONF_CONFIG_FLOW


async def test_flow_import_already_configured(hass: HomeAssistant):
    """Test import step already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="123456789012345678901234", data=CONF_CONFIG_FLOW
    )

    entry.add_to_hass(hass)

    with _patch_skybell():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_step_reauth(hass: HomeAssistant):
    """Test the reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="123456789012345678901234", data=CONF_CONFIG_FLOW
    )

    entry.add_to_hass(hass)

    with patch("skybellpy.UTILS"):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=entry.data,
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        with _patch_skybell():
            new_conf = {CONF_EMAIL: "user@email.com", CONF_PASSWORD: "password2"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=new_conf,
            )

            assert result2["type"] == RESULT_TYPE_ABORT
            assert result2["reason"] == "reauth_successful"
            assert entry.data == new_conf
