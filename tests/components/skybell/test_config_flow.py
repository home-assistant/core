"""Test SkyBell config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.skybell.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONF_DATA, PASSWORD, USER_ID, patch_skybell, patch_skybell_devices

from tests.common import MockConfigEntry


def _patch_setup_entry() -> None:
    return patch(
        "homeassistant.components.skybell.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    with patch_skybell(), patch_skybell_devices(), _patch_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "user"
        assert result["data"] == CONF_DATA
        assert result["result"].unique_id == USER_ID


async def test_flow_user_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test user initialized flow with duplicate server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass: HomeAssistant, cannot_connect) -> None:
    """Test user initialized flow with unreachable server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_credentials(hass: HomeAssistant, invalid_auth) -> None:
    """Test that invalid credentials throws an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_unknown_error(
    hass: HomeAssistant, internal_server_error
) -> None:
    """Test user initialized flow with unreachable server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_step_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the reauth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
        },
        data=config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch_skybell(), patch_skybell_devices(), _patch_setup_entry():

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


async def test_step_reauth_failed(
    hass: HomeAssistant, config_entry: MockConfigEntry, invalid_auth
) -> None:
    """Test the reauth flow fails and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
        },
        data=config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch_skybell(), patch_skybell_devices(), _patch_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
