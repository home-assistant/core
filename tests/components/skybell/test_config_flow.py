"""Test SkyBell config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.skybell.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    CONF_DATA,
    PASSWORD,
    USER_ID,
    create_skybell,
    mock_skybell,
    set_aioclient_responses,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _mock_skybell(hass: HomeAssistant) -> None:
    """Mock Skybell config flow object."""
    return patch(
        "homeassistant.components.skybell.config_flow.Skybell",
        return_value=create_skybell(hass),
    )


def _patch_setup_entry() -> None:
    return patch(
        "homeassistant.components.skybell.async_setup_entry", return_value=True
    )


async def test_flow_user(hass: HomeAssistant, connection) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with _mock_skybell(hass), _patch_setup_entry():
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


async def test_step_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, connection
) -> None:
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

    with mock_skybell(hass), _mock_skybell(hass):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_step_reauth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    invalid_auth,
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

    aioclient_mock.clear_requests()
    await set_aioclient_responses(aioclient_mock)

    with mock_skybell(hass), _mock_skybell(hass):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
