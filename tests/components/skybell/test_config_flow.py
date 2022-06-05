"""Test SkyBell config flow."""
from unittest.mock import patch

from aioskybell import exceptions

from homeassistant.components.skybell.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import CONF_CONFIG_FLOW, _patch_skybell, _patch_skybell_devices

from tests.common import MockConfigEntry


def _patch_setup_entry() -> None:
    return patch(
        "homeassistant.components.skybell.async_setup_entry",
        return_value=True,
    )


def _patch_setup() -> None:
    return patch(
        "homeassistant.components.skybell.async_setup",
        return_value=True,
    )


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with _patch_skybell(), _patch_skybell_devices(), _patch_setup_entry(), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "user"
        assert result["data"] == CONF_CONFIG_FLOW


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with _patch_skybell() as skybell_mock:
        skybell_mock.side_effect = exceptions.SkybellException(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test that invalid credentials throws an error."""
    with patch("homeassistant.components.skybell.Skybell.async_login") as skybell_mock:
        skybell_mock.side_effect = exceptions.SkybellAuthenticationException(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    with _patch_skybell_devices() as skybell_mock:
        skybell_mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test import step."""
    with _patch_skybell(), _patch_skybell_devices(), _patch_setup_entry(), _patch_setup():
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


async def test_flow_import_already_configured(hass: HomeAssistant) -> None:
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
