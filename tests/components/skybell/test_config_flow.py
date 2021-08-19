"""Test SkyBell config flow."""
from unittest.mock import patch

from requests.exceptions import ConnectTimeout
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

from . import (
    CONF_CONFIG_FLOW,
    _create_mocked_skybell,
    _patch_config_flow_skybell,
    _patch_skybell_login,
)

from tests.common import MockConfigEntry


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )


def _patch_setup():
    return patch(
        "homeassistant.components.skybell.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass):
    """Test that the user step works."""
    conf = {CONF_EMAIL: "user@email.com", CONF_PASSWORD: "password"}

    with patch("homeassistant.components.skybell.config_flow.Skybell"), patch(
        "skybellpy.UTILS"
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user@email.com"
        assert result["data"] == {
            CONF_EMAIL: "user@email.com",
            CONF_PASSWORD: "password",
        }


async def test_flow_user_already_configured(hass):
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


async def test_flow_user_cannot_connect(hass):
    """Test user initialized flow with unreachable server."""
    mocked_skybell = await _create_mocked_skybell(True)
    with _patch_config_flow_skybell(mocked_skybell) as skybellmock:
        skybellmock.side_effect = ConnectTimeout
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    mocked_skybell = await _create_mocked_skybell(True)
    with _patch_skybell_login(mocked_skybell) as skybellmock:
        skybellmock.side_effect = exceptions.SkybellAuthenticationException
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_unknown_error(hass):
    """Test user initialized flow with unreachable server."""
    mocked_skybell = await _create_mocked_skybell(True)
    with _patch_config_flow_skybell(mocked_skybell) as skybellmock:
        skybellmock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}


async def test_flow_import(hass):
    """Test import step."""
    mocked_skybell = await _create_mocked_skybell()
    with _patch_config_flow_skybell(mocked_skybell), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
    )

    entry.add_to_hass(hass)

    with _patch_config_flow_skybell(mocked_skybell), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_step_reauth(hass: HomeAssistant):
    """Test the reauth flow."""
    conf = {CONF_EMAIL: "user@email.com", CONF_PASSWORD: "password"}
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="user@email.com", data=conf, entry_id="test"
    )

    entry.add_to_hass(hass)

    with patch("homeassistant.components.skybell.config_flow.Skybell"), patch(
        "skybellpy.UTILS"
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=entry.data,
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        with patch("homeassistant.config_entries.ConfigEntries.async_reload"):

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_EMAIL: "user@email.com", CONF_PASSWORD: "password2"},
            )

            assert result["type"] == RESULT_TYPE_ABORT
            assert result["reason"] == "reauth_successful"

        assert len(hass.config_entries.async_entries()) == 1
