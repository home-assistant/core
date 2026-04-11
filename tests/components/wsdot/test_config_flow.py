"""Define tests for the wsdot config flow."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from wsdot import WsdotTravelError

from homeassistant.components.wsdot.const import (
    CONF_TRAVEL_TIMES,
    DOMAIN,
    SUBENTRY_TRAVEL_TIMES,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
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
async def test_errors(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_setup_entry: AsyncMock,
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

    # User data; the user made a choice and hit submit
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TRAVEL_TIMES),
        context={"source": SOURCE_USER},
        data=VALID_USER_TRAVEL_TIME_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NAME] == "Seattle-Bellevue via I-90 (EB AM)"
    assert result["data"][CONF_ID] == 96


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
    import_config: dict[str, str | int],
) -> None:
    """Test that the yaml import works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_config,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "wsdot"
    assert result["data"][CONF_API_KEY] == "abcd-5678"

    entry = result["result"]
    assert entry is not None
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TRAVEL_TIMES
    assert subentry.title == "Seattle-Bellevue via I-90 (EB AM)"
    assert subentry.data[CONF_NAME] == "Seattle-Bellevue via I-90 (EB AM)"
    assert subentry.data[CONF_ID] == 96


@pytest.mark.parametrize(
    ("failed_travel_time_status", "abort_reason"),
    [
        (400, "invalid_api_key"),
        (404, "cannot_connect"),
    ],
)
async def test_failed_import_entry(
    hass: HomeAssistant,
    mock_failed_travel_time: AsyncMock,
    mock_config_data: dict[str, Any],
    failed_travel_time_status: int,
    abort_reason: str,
) -> None:
    """Test the failure modes of a yaml import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=mock_config_data,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


async def test_incorrect_import_entry(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_config_data: dict[str, Any],
) -> None:
    """Test a yaml import of a non-existent route."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: "abcd-5678",
            CONF_TRAVEL_TIMES: [{CONF_ID: "100001", CONF_NAME: "nowhere"}],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_travel_time_id"


async def test_import_integration_already_exists(
    hass: HomeAssistant,
    mock_travel_time: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test we only allow one entry per API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_API_KEY: "abcd-1234",
            CONF_TRAVEL_TIMES: [{CONF_ID: "100001", CONF_NAME: "nowhere"}],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
