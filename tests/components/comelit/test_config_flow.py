"""Tests for Comelit SimpleHome config flow."""

from typing import Any
from unittest.mock import patch

from aiocomelit import CannotAuthenticate, CannotConnect
import pytest

from homeassistant.components.comelit.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import FAKE_PIN, MOCK_USER_BRIDGE_DATA, MOCK_USER_VEDO_DATA

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("class_api", "user_input"),
    [
        ("ComeliteSerialBridgeApi", MOCK_USER_BRIDGE_DATA),
        ("ComelitVedoApi", MOCK_USER_VEDO_DATA),
    ],
)
async def test_full_flow(
    hass: HomeAssistant, class_api: str, user_input: dict[str, Any]
) -> None:
    """Test starting a flow by user."""
    with (
        patch(
            f"aiocomelit.api.{class_api}.login",
        ),
        patch(
            f"aiocomelit.api.{class_api}.logout",
        ),
        patch("homeassistant.components.comelit.async_setup_entry") as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == user_input[CONF_HOST]
        assert result["data"][CONF_PORT] == user_input[CONF_PORT]
        assert result["data"][CONF_PIN] == user_input[CONF_PIN]
        assert not result["result"].unique_id
        await hass.async_block_till_done()

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_exception_connection(hass: HomeAssistant, side_effect, error) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with (
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.login",
            side_effect=side_effect,
        ),
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.logout",
        ),
        patch(
            "homeassistant.components.comelit.async_setup_entry",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_BRIDGE_DATA
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] is not None
        assert result["errors"]["base"] == error


async def test_reauth_successful(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_BRIDGE_DATA)
    mock_config.add_to_hass(hass)

    with (
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.login",
        ),
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.logout",
        ),
        patch("homeassistant.components.comelit.async_setup_entry"),
        patch("requests.get") as mock_request_get,
    ):
        mock_request_get.return_value.status_code = 200

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
            data=mock_config.data,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PIN: FAKE_PIN,
            },
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (CannotConnect, "cannot_connect"),
        (CannotAuthenticate, "invalid_auth"),
        (ConnectionResetError, "unknown"),
    ],
)
async def test_reauth_not_successful(hass: HomeAssistant, side_effect, error) -> None:
    """Test starting a reauthentication flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_BRIDGE_DATA)
    mock_config.add_to_hass(hass)

    with (
        patch("aiocomelit.api.ComeliteSerialBridgeApi.login", side_effect=side_effect),
        patch(
            "aiocomelit.api.ComeliteSerialBridgeApi.logout",
        ),
        patch("homeassistant.components.comelit.async_setup_entry"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config.entry_id},
            data=mock_config.data,
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PIN: FAKE_PIN,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] is not None
        assert result["errors"]["base"] == error
