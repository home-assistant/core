"""Test the Komfovent config flow."""
from unittest.mock import AsyncMock, patch

import komfovent_api
import pytest

from homeassistant import config_entries
from homeassistant.components.komfovent.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test flow completes as expected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    await __test_normal_flow(hass, mock_setup_entry, result["flow_id"])


@pytest.mark.parametrize(
    ("error", "expected_response"),
    [
        (komfovent_api.KomfoventConnectionResult.NOT_FOUND, "cannot_connect"),
        (komfovent_api.KomfoventConnectionResult.UNAUTHORISED, "invalid_auth"),
        (komfovent_api.KomfoventConnectionResult.INVALID_INPUT, "invalid_input"),
    ],
)
async def test_form_error_handling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    error: komfovent_api.KomfoventConnectionResult,
    expected_response: str,
) -> None:
    """Test errors during flow are handled and dont affect final result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_credentials",
        return_value=(
            error,
            None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_response}

    await __test_normal_flow(hass, mock_setup_entry, result2["flow_id"])


async def __test_normal_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, flow_id: str
) -> None:
    """Test flow completing as expected, no matter what happened before."""

    with patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_credentials",
        return_value=(
            komfovent_api.KomfoventConnectionResult.SUCCESS,
            komfovent_api.KomfoventCredentials("1.1.1.1", "user", "pass"),
        ),
    ), patch(
        "homeassistant.components.komfovent.config_flow.komfovent_api.get_settings",
        return_value=(
            komfovent_api.KomfoventConnectionResult.SUCCESS,
            komfovent_api.KomfoventSettings("test-name", None, None, None),
        ),
    ):
        final_result = await hass.config_entries.flow.async_configure(
            flow_id,
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert final_result["type"] == FlowResultType.CREATE_ENTRY
    assert final_result["title"] == "test-name"
    assert final_result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
