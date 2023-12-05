"""Test the A. O. Smith config flow."""
from unittest.mock import AsyncMock, patch

from py_aosmith import AOSmithInvalidCredentialsException
import pytest

from homeassistant import config_entries
from homeassistant.components.aosmith.const import DOMAIN
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.components.aosmith.conftest import FIXTURE_USER_INPUT

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        return_value=[],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "testemail@example.com"
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=AOSmithInvalidCredentialsException("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth works."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_USER_INPUT[CONF_EMAIL],
        data=FIXTURE_USER_INPUT,
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=AOSmithInvalidCredentialsException("Invalid credentials"),
    ), patch(
        "homeassistant.components.aosmith.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config.entry_id,
            },
            data=FIXTURE_USER_INPUT,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        return_value=[],
    ), patch("homeassistant.components.aosmith.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
