"""Test SkyBell config flow."""

from unittest.mock import patch

from aioskybell import exceptions
import pytest

from homeassistant.components.skybell.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONF_DATA, PASSWORD, USER_ID

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def setup_entry() -> None:
    """Make sure component doesn't initialize."""
    with patch(
        "homeassistant.components.skybell.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user"
    assert result["data"] == CONF_DATA
    assert result["result"].unique_id == USER_ID


async def test_flow_user_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
    )

    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_cannot_connect(hass: HomeAssistant, skybell_mock) -> None:
    """Test user initialized flow with unreachable server."""
    skybell_mock.async_initialize.side_effect = exceptions.SkybellException(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_credentials(hass: HomeAssistant, skybell_mock) -> None:
    """Test that invalid credentials throws an error."""
    skybell_mock.async_initialize.side_effect = (
        exceptions.SkybellAuthenticationException(hass)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_unknown_error(hass: HomeAssistant, skybell_mock) -> None:
    """Test user initialized flow with unreachable server."""
    skybell_mock.async_initialize.side_effect = Exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_step_reauth(hass: HomeAssistant) -> None:
    """Test the reauth flow."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=USER_ID, data=CONF_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_step_reauth_failed(hass: HomeAssistant, skybell_mock) -> None:
    """Test the reauth flow fails and recovers."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=USER_ID, data=CONF_DATA)
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    skybell_mock.async_initialize.side_effect = (
        exceptions.SkybellAuthenticationException(hass)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    skybell_mock.async_initialize.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
