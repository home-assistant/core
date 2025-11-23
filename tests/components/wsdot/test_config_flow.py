"""Define tests for the wsdot config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from wsdot import TravelTime, WsdotTravelError

from homeassistant.components.configurator import ATTR_ERRORS
from homeassistant.components.wsdot.const import (
    CONF_TRAVEL_TIMES,
    DOMAIN,
    SUBENTRY_TRAVEL_TIMES,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BASE,
    CONF_ID,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONF_STEP_ID = "step_id"
CONF_REASON = "reason"

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
        DOMAIN, context={'source': SOURCE_USER}
    )

    assert result['type'] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == SOURCE_USER

    # User data; the user entered data and hit submit
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_CONFIG,
    )

    assert result['type'] is FlowResultType.CREATE_ENTRY
    assert result['title'] == DOMAIN
    assert result['data'][CONF_API_KEY] == "abcd-1234"


@pytest.mark.parametrize(
    "mock_subentries",
    [
        [],
    ],
    ids=[""],
)
async def test_create_travel_time_subentry(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test that the user step for Travel Time works."""
    # No user data; form is being show for the first time
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TRAVEL_TIMES), context={'source': SOURCE_USER}
    )

    assert result['type'] is FlowResultType.FORM
    assert result[CONF_STEP_ID] == SOURCE_USER

    # User data; the user made a choice and hit submit
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TRAVEL_TIMES),
        context={'source': SOURCE_USER},
        data=VALID_USER_TRAVEL_TIME_CONFIG,
    )

    assert result['type'] is FlowResultType.CREATE_ENTRY
    assert result['data'][CONF_NAME] == "Seattle-Bellevue via I-90 (EB AM)"
    assert result['data'][CONF_ID] == 96


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
        context={'source': SOURCE_IMPORT},
        data=import_config,
    )

    assert result['type'] is FlowResultType.CREATE_ENTRY
    assert result['title'] == "wsdot"
    assert result['data'][CONF_API_KEY] == "abcd-5678"

    entry = result["result"]
    assert entry is not None
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TRAVEL_TIMES
    assert subentry.title == "Seattle-Bellevue via I-90 (EB AM)"
    assert subentry.data[CONF_NAME] == "Seattle-Bellevue via I-90 (EB AM)"
    assert subentry.data[CONF_ID] == 96


async def test_integration_already_exists(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test we only allow one entry per API key."""
    duplicate_config_flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={'source': SOURCE_USER},
        data=VALID_USER_CONFIG,
    )

    assert duplicate_config_flow['type'] is FlowResultType.ABORT
    assert duplicate_config_flow[CONF_REASON] == "already_configured"


async def test_travel_route_already_exists(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test we only allow choosing a travel time route once."""
    duplicate_config_flow = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TRAVEL_TIMES),
        context={'source': SOURCE_USER},
        data=VALID_USER_TRAVEL_TIME_CONFIG,
    )

    assert duplicate_config_flow['type'] is FlowResultType.ABORT
    assert duplicate_config_flow[CONF_REASON] == "already_configured"


async def test_api_not_valid(
    hass: HomeAssistant,
    mock_travel_time: TravelTime,
) -> None:
    """Test that an auth error to the service returns the user an error flow."""
    # put a patch on the patch to simulate the error
    # the fixture patch protects this test from making any network requests
    with patch("wsdot.WsdotTravelTimes") as mock:
        client = mock.return_value
        client.get_travel_time.side_effect = WsdotTravelError()
        client.get_all_travel_times.side_effect = WsdotTravelError()
        config_flow = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': SOURCE_USER},
            data=VALID_USER_CONFIG,
        )

    assert config_flow['type'] is FlowResultType.FORM
    assert config_flow[ATTR_ERRORS][CONF_BASE] == "cannot_connect"

    config_flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={'source': SOURCE_USER},
        data=VALID_USER_CONFIG,
    )
    assert config_flow['type'] is FlowResultType.CREATE_ENTRY
