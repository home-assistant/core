"""Define tests for the wsdot config flow."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.components.wsdot.config_flow import DIALOG_API_KEY, DIALOG_NAME
from homeassistant.components.wsdot.sensor import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TRAVEL_TIMES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_SOURCE, CONF_TYPE
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

VALID_IMPORT_CONFIG = {
    CONF_API_KEY: "abcd-5678",
    CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I-90 EB"}],
}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result[CONF_TYPE] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == SOURCE_USER


async def test_create_user_entry(
    hass: HomeAssistant, mock_travel_time: AsyncMock
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
    assert result[CONF_DATA][CONF_TRAVEL_TIMES] == [
        {"id": 96, "name": "Seattle-Bellevue via I-90 (EB AM)"}
    ]


async def test_create_import_entry(
    hass: HomeAssistant, mock_travel_time: AsyncMock, mock_config_data: dict[str, Any]
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=VALID_IMPORT_CONFIG,
    )

    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_TITLE] == "wsdot"
    assert result[CONF_DATA][CONF_API_KEY] == "abcd-5678"
    assert result[CONF_DATA][CONF_TRAVEL_TIMES] == [{"id": 96, "name": "I-90 EB"}]


async def test_integration_already_exists(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_travel_time: AsyncMock
) -> None:
    """Test we only allow a single config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_CONFIG,
    )

    assert result[CONF_TYPE] is FlowResultType.ABORT
    assert result[CONF_REASON] == "single_instance_allowed"
