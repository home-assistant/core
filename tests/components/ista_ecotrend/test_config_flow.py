"""Test the ista EcoTrend config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyecotrend_ista import LoginError, ServerError
import pytest

from homeassistant.components.ista_ecotrend.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ista")
async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Max Istamann"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (LoginError(None), "invalid_auth"),
        (ServerError, "cannot_connect"),
        (IndexError, "unknown"),
    ],
)
async def test_form_error_and_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_ista: MagicMock,
    side_effect: Exception,
    error_text: str,
) -> None:
    """Test config flow error and recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_ista.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    mock_ista.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Max Istamann"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_ista")
async def test_reauth(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""

    ista_config_entry.add_to_hass(hass)

    result = await ista_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert ista_config_entry.data == {
        CONF_EMAIL: "new@example.com",
        CONF_PASSWORD: "new-password",
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_text"),
    [
        (LoginError(None), "invalid_auth"),
        (ServerError, "cannot_connect"),
        (IndexError, "unknown"),
    ],
)
async def test_reauth_error_and_recover(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    mock_ista: MagicMock,
    side_effect: Exception,
    error_text: str,
) -> None:
    """Test reauth flow error and recover."""

    ista_config_entry.add_to_hass(hass)

    result = await ista_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_ista.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    mock_ista.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert ista_config_entry.data == {
        CONF_EMAIL: "new@example.com",
        CONF_PASSWORD: "new-password",
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_ista")
async def test_form__already_configured(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
) -> None:
    """Test we abort form login when entry is already configured."""

    ista_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_ista")
async def test_flow_reauth_unique_id_mismatch(hass: HomeAssistant) -> None:
    """Test reauth flow unique id mismatch."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
        unique_id="42243134-21f6-40a2-a79f-e417a3a12104",
    )

    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "new@example.com",
            CONF_PASSWORD: "new-password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    assert len(hass.config_entries.async_entries()) == 1
