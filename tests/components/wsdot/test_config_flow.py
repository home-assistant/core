"""Define tests for the wsdot config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.wsdot.config_flow import CONF_NAME, CONF_API_KEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_NAME: "wsdot",
    CONF_API_KEY: "abcd-1234",
}

async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(
    hass: HomeAssistant, mock_wsdot_client: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "wsdot"
    assert result["data"]["api_key"] == "abcd-1234"
    assert result["data"]["travel_time"] == [{"id": "96", "name": "Seattle-Bellevue via I-90 (EB AM)"}]


async def test_integration_already_exists(
    hass: HomeAssistant, mock_wsdot_client: AsyncMock
) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="96",
        data= {
            "api_key": "efgh-5678",
            "travel_time": [
                {"id": "96", "name": "Seattle-Bellevue via I-90 (EB AM)"},
            ],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"