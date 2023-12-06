"""Test the A. O. Smith config flow."""
from unittest.mock import AsyncMock, patch

from py_aosmith import AOSmithInvalidCredentialsException
import pytest

from homeassistant import config_entries
from homeassistant.components.aosmith.const import DOMAIN
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.aosmith.conftest import FIXTURE_USER_INPUT


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
    assert result2["title"] == FIXTURE_USER_INPUT[CONF_EMAIL]
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error_key"),
    [
        (AOSmithInvalidCredentialsException("Invalid credentials"), "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_form_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error_key: str,
) -> None:
    """Test handling an exception and then recovering on the second attempt."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": expected_error_key}

    with patch(
        "homeassistant.components.aosmith.config_flow.AOSmithAPIClient.get_devices",
        return_value=[],
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == FIXTURE_USER_INPUT[CONF_EMAIL]
    assert result3["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1
