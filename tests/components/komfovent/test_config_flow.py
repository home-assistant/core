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
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-name"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


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
    error: komfovent_api.KomfoventConnectionResult,
    expected_response: str,
) -> None:
    """Test we handle invalid auth."""
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
