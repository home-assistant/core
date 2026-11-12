"""Test the NEPViewer config flow."""

from unittest.mock import MagicMock

from aionepviewer import NepAuthError, NepConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.nepviewer.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_EMAIL: "test@example.com",
    CONF_PASSWORD: "test_password",
}


async def test_form_shows_user_step(hass: HomeAssistant) -> None:
    """Test that the user form is shown correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_form_creates_entry(
    hass: HomeAssistant, mock_nepviewer_config_flow: MagicMock
) -> None:
    """Test that a valid login creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USER_INPUT[CONF_EMAIL]
    assert result["data"] == USER_INPUT


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(NepAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(NepConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_nepviewer_config_flow: MagicMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test that errors are shown for auth, connection and unknown failures."""
    mock_nepviewer_config_flow.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Recover from the error by fixing credentials
    mock_nepviewer_config_flow.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_nepviewer_config_flow: MagicMock
) -> None:
    """Test that duplicate entries are rejected."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_uid",
        data=USER_INPUT,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer_config_flow: MagicMock,
) -> None:
    """Test that the reauth flow succeeds with a valid new password."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new_password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(NepAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(NepConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nepviewer_config_flow: MagicMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test that the reauth form shows errors and recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_nepviewer_config_flow.authenticate.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "bad_password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_nepviewer_config_flow.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new_password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
