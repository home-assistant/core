"""Test the Brunt config flow."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ServerDisconnectedError
import pytest

from homeassistant import config_entries
from homeassistant.components.brunt.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.brunt.config_flow.BruntClientAsync.async_login",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_login(hass: HomeAssistant) -> None:
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        title="test-username",
        unique_id="test-username",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.brunt.config_flow.BruntClientAsync.async_login",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=CONFIG
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (ServerDisconnectedError, "cannot_connect"),
        (ClientResponseError(Mock(), None, status=403), "invalid_auth"),
        (ClientResponseError(Mock(), None, status=401), "unknown"),
        (Exception, "unknown"),
    ],
)
async def test_form_error(hass: HomeAssistant, side_effect, error_message) -> None:
    """Test we handle cannot connect."""
    with patch(
        "homeassistant.components.brunt.config_flow.BruntClientAsync.async_login",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=CONFIG
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error_message}


@pytest.mark.parametrize(
    ("side_effect", "result_type", "password", "step_id", "reason"),
    [
        (None, FlowResultType.ABORT, "test", None, "reauth_successful"),
        (
            Exception,
            FlowResultType.FORM,
            CONFIG[CONF_PASSWORD],
            "reauth_confirm",
            None,
        ),
    ],
)
async def test_reauth(
    hass: HomeAssistant, side_effect, result_type, password, step_id, reason
) -> None:
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        title="test-username",
        unique_id="test-username",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    with patch(
        "homeassistant.components.brunt.config_flow.BruntClientAsync.async_login",
        return_value=None,
        side_effect=side_effect,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"password": "test"},
        )
        assert result3["type"] == result_type
        assert entry.data["password"] == password
        assert result3.get("step_id", None) == step_id
        assert result3.get("reason", None) == reason
