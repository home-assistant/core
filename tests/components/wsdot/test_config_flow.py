"""Define tests for the wsdot config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.wsdot.const import (
    CONF_DATA,
    CONF_TITLE,
    CONF_TRAVEL_TIMES,
    DOMAIN,
    SUBENTRY_TRAVEL_TIMES,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME, CONF_SOURCE, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

CONF_STEP_ID = "step_id"
CONF_REASON = "reason"

VALID_USER_CONFIG = {
    CONF_API_KEY: "abcd-1234",
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


@pytest.mark.parametrize(
    "import_config",
    [
        {
            CONF_API_KEY: "abcd-5678",
            CONF_TRAVEL_TIMES: [{CONF_ID: 96, CONF_NAME: "I-90 EB"}],
        },
        {
            CONF_API_KEY: "abcd-5678",
            CONF_TRAVEL_TIMES: [{CONF_ID: "96", CONF_NAME: "I-90 EB"}],
        },
    ],
    ids=["with-int-id", "with-str-id"],
)
async def test_create_import_entry(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_data: dict[str, Any],
    import_config: dict[str, str | int],
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_IMPORT},
        data=import_config,
    )

    assert result[CONF_TYPE] is FlowResultType.CREATE_ENTRY
    assert result[CONF_TITLE] == "wsdot"
    assert result[CONF_DATA][CONF_API_KEY] == "abcd-5678"

    route = next(iter(result.get("subentries", [])), None)
    assert route is not None
    assert route["subentry_type"] == SUBENTRY_TRAVEL_TIMES
    assert route[CONF_TITLE] == "Seattle-Bellevue via I-90 (EB AM)"
    assert route[CONF_DATA][CONF_NAME] == "Seattle-Bellevue via I-90 (EB AM)"
    assert route[CONF_DATA][CONF_ID] == 96


async def test_integration_already_exists(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
) -> None:
    """Test we only allow a single config flow."""
    first_config_flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_CONFIG,
    )

    assert first_config_flow[CONF_TYPE] is FlowResultType.CREATE_ENTRY

    duplicate_config_flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_CONFIG,
    )

    assert duplicate_config_flow[CONF_TYPE] is FlowResultType.ABORT
    assert duplicate_config_flow[CONF_REASON] == "already_configured"
