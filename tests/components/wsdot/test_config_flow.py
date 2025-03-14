"""Define tests for the wsdot config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.wsdot.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_TRAVEL_TIMES,
    CONF_TRAVEL_TIMES_ID,
    CONF_TRAVEL_TIMES_NAME,
    DIALOG_API_KEY,
    DIALOG_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_SOURCE,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONF_TITLE = "title"
CONF_STEP_ID = "step_id"
CONF_DATA = "data"
CONF_REASON = "reason"

VALID_USER_CONFIG = {
    DIALOG_NAME: "wsdot",
    DIALOG_API_KEY: "abcd-1234",
}

async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == SOURCE_USER


async def test_create_entry(
    hass: HomeAssistant, mock_wsdot_client: AsyncMock
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=VALID_USER_CONFIG,
    )

    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_TITLE] == "wsdot"
    assert result[CONF_DATA][CONF_API_KEY] == "abcd-1234"
    assert result[CONF_DATA][CONF_TRAVEL_TIMES] == [{CONF_TRAVEL_TIMES_ID: "96", CONF_TRAVEL_TIMES_NAME: "Seattle-Bellevue via I-90 (EB AM)"}]


async def test_integration_already_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wsdot_client: AsyncMock
) -> None:
    """Test we only allow a single config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_CONFIG,
    )

    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == "already_configured"