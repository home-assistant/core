"""Test the Compit config flow."""

from unittest.mock import patch

from compit_inext_api import Gate, SystemInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.compit.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_INPUT = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "password",
}


@pytest.fixture
def mock_reauth_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com"},
        unique_id=CONFIG_INPUT[CONF_EMAIL],
    )


async def test_async_step_user_success(hass: HomeAssistant) -> None:
    """Test user step with successful authentication."""
    with (
        patch(
            "homeassistant.components.compit.config_flow.CompitApiConnector.init",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_INPUT
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == CONFIG_INPUT[CONF_EMAIL]
        assert result["data"] == CONFIG_INPUT


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_async_step_user_invalid(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step with invalid authentication."""
    with (
        patch(
            "homeassistant.components.compit.config_flow.CompitApiConnector.init",
            side_effect=exception,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}


async def test_async_step_reauth_confirm_success(
    hass: HomeAssistant, mock_reauth_entry: MockConfigEntry
) -> None:
    """Test reauth confirm step with successful authentication."""
    with (
        patch(
            "homeassistant.components.compit.config_flow.CompitApiConnector.init",
            return_value=True,
        ),
    ):
        mock_reauth_entry.add_to_hass(hass)

        result = await mock_reauth_entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert mock_reauth_entry.data == {
            CONF_EMAIL: CONFIG_INPUT[CONF_EMAIL],
            CONF_PASSWORD: "new-password",
        }


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_async_step_reauth_confirm_invalid(
    hass: HomeAssistant,
    mock_reauth_entry: MockConfigEntry,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test reauth confirm step with invalid authentication."""
    with (
        patch(
            "homeassistant.components.compit.config_flow.CompitApiConnector.init",
            side_effect=exception,
        ),
    ):
        mock_reauth_entry.add_to_hass(hass)

        result = await mock_reauth_entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}


async def test_async_step_user_success_after_error(hass: HomeAssistant) -> None:
    """Test user step succeeds after an error is cleared."""
    with patch(
        "homeassistant.components.compit.config_flow.CompitApiConnector.init",
        side_effect=[
            CannotConnect,
            True,
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_entries.SOURCE_USER

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG_INPUT
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == CONFIG_INPUT[CONF_EMAIL]
        assert result["data"] == CONFIG_INPUT


async def test_async_step_reauth_confirm_success_after_error(
    hass: HomeAssistant, mock_reauth_entry: MockConfigEntry
) -> None:
    """Test reauth confirm step succeeds after an error is cleared."""
    with patch(
        "homeassistant.components.compit.config_flow.CompitApiConnector.init",
        side_effect=[
            InvalidAuth,
            True,
        ],
    ):
        mock_reauth_entry.add_to_hass(hass)

        result = await mock_reauth_entry.start_reauth_flow(hass)
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: CONFIG_INPUT[CONF_EMAIL], CONF_PASSWORD: "correct-password"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert mock_reauth_entry.data == {
            CONF_EMAIL: CONFIG_INPUT[CONF_EMAIL],
            CONF_PASSWORD: "correct-password",
        }
