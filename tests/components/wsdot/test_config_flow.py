"""Define tests for the wsdot config flow."""

from unittest.mock import AsyncMock

import pytest
from wsdot import WsdotTravelError

from homeassistant.components.wsdot.const import DOMAIN, SUBENTRY_TRAVEL_TIMES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALID_USER_CONFIG = {
    CONF_API_KEY: "abcd-1234",
}

VALID_USER_TRAVEL_TIME_CONFIG = {
    CONF_NAME: "Seattle-Bellevue via I-90 (EB AM)",
}


async def test_create_user_entry(
    hass: HomeAssistant, mock_travel_time: AsyncMock
) -> None:
    """Test that the user step works."""
    # No user data; form is being show for the first time
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # User data; the user entered data and hit submit
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"][CONF_API_KEY] == "abcd-1234"


@pytest.mark.parametrize(
    ("failed_travel_time_status", "errors"),
    [
        (400, {CONF_API_KEY: "invalid_api_key"}),
        (404, {"base": "cannot_connect"}),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_errors(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    failed_travel_time_status: int,
    errors: dict[str, str],
) -> None:
    """Test that the user step works."""
    mock_travel_time.get_all_travel_times.side_effect = WsdotTravelError(
        status=failed_travel_time_status
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors

    mock_travel_time.get_all_travel_times.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "mock_subentries",
    [
        [],
    ],
)
async def test_create_travel_time_subentry(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that the user step for Travel Time works."""
    # No user data; form is being show for the first time
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TRAVEL_TIMES),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # User data; the user made a choice and hit submit
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        VALID_USER_TRAVEL_TIME_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NAME] == "Seattle-Bellevue via I-90 (EB AM)"
    assert result["data"][CONF_ID] == 96


async def test_integration_already_exists(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test we only allow one entry per API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_travel_route_already_exists(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test we only allow choosing a travel time route once."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TRAVEL_TIMES),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input=VALID_USER_TRAVEL_TIME_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
