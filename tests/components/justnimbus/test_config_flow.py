"""Test the JustNimbus config flow."""
from unittest.mock import patch

from justnimbus.exceptions import InvalidClientID, JustNimbusError
import pytest

from homeassistant import config_entries
from homeassistant.components.justnimbus.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None


@pytest.mark.parametrize(
    "side_effect,errors",
    (
        (
            InvalidClientID(client_id="test_id"),
            {"base": "invalid_auth"},
        ),
        (
            JustNimbusError(),
            {"base": "cannot_connect"},
        ),
    ),
)
async def test_form_errors(
    hass: HomeAssistant,
    side_effect: JustNimbusError,
    errors: dict,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client_id = "test_id"

    with patch(
        "justnimbus.JustNimbusClient.get_data",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: mock_client_id,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == errors

    # check if it's still possible to configure the integration/no weird side-effects were caused
    await test_form(hass=hass)
