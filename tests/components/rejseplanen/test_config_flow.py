"""Test the Rejseplanen config flow."""

import logging
from unittest.mock import AsyncMock, patch

from py_rejseplan import enums
import pytest

from homeassistant import config_entries
from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value

LOGGER = logging.getLogger(__name__)

TEST_API_KEY = "api_key"


async def test_form_user_step(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_api: AsyncMock
) -> None:
    """Test the user step of the Rejseplanen config flow.

    This test verifies that:
    - The initial form is presented to the user when starting the config flow.
    - Submitting a valid API key results in the creation of a config entry with the correct title and data.
    - The authentication key validation is properly mocked to simulate a successful validation.
    """

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.rejseplanen.config_flow.Rejseplanen.validate_auth_key",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Rejseplanen"
    assert result["data"] == {"api_key": TEST_API_KEY}

    assert len(mock_setup_entry.mock_calls) == 1


#         try:
#             result = await self.hass.async_add_executor_job(api.validate_auth_key)
#         except (ConnectionError, TimeoutError, OSError):
#             errors["base"] = "cannot_connect"
#         else:
#             if not result:
#                 errors["base"] = "invalid_auth"


@pytest.mark.parametrize(
    ("patch_args", "expected_errors"),
    [
        # Invalid authentication
        (
            {"return_value": False, "side_effect": None},
            {"base": "invalid_auth"},
        ),
        # API connection exception
        (
            {"return_value": True, "side_effect": ConnectionError("Connection failed")},
            {"base": "cannot_connect"},
        ),
        (
            {"return_value": True, "side_effect": TimeoutError("Network Timeout")},
            {"base": "cannot_connect"},
        ),
        (
            {"return_value": True, "side_effect": OSError("OS Error")},
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_config_flow_error_cases(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    patch_args,
    expected_errors,
) -> None:
    """Test invalid authentication handling."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.rejseplanen.config_flow.Rejseplanen"
    ) as mock_client:
        mock_client.return_value.validate_auth_key.return_value = patch_args[
            "return_value"
        ]
        mock_client.return_value.validate_auth_key.side_effect = patch_args[
            "side_effect"
        ]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors

    data_schema = result["data_schema"].schema
    assert get_schema_suggested_value(data_schema, CONF_API_KEY) == TEST_API_KEY

    with patch(
        "homeassistant.components.rejseplanen.config_flow.Rejseplanen"
    ) as mock_client:
        mock_client.return_value.validate_auth_key.return_value = True
        mock_client.return_value.validate_auth_key.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_singleton_prevention(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test singleton integration prevents multiple entries."""

    mock_config_entry.add_to_hass(hass)

    # Try to start new config flow - should abort for singleton
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("user_input", "expected_title", "expected_data"),
    [
        # Minimal input, only required fields
        (
            {CONF_STOP_ID: "12345", CONF_NAME: "Central Station"},
            "Central Station",
            {
                CONF_STOP_ID: 12345,
                CONF_NAME: "Central Station",
                "departure_type": [],
                "direction": [],
                "route": [],
            },
        ),
        # All optional fields provided, single values
        (
            {
                CONF_STOP_ID: "67890",
                CONF_NAME: "Airport",
                "departure_type": ["bus"],
                "direction": ["North"],
            },
            "Airport",
            {
                CONF_STOP_ID: 67890,
                CONF_NAME: "Airport",
                "departure_type": [enums.TransportClass.BUS],
                "direction": ["North"],
                "route": [],
            },
        ),
        # All optional fields provided, multiple values
        (
            {
                CONF_STOP_ID: "24680",
                CONF_NAME: "Harbor",
                "departure_type": ["bus", "tog"],
                "direction": ["East", "West"],
            },
            "Harbor",
            {
                CONF_STOP_ID: 24680,
                CONF_NAME: "Harbor",
                "departure_type": [
                    enums.TransportClass.BUS,
                    enums.TransportClass.TOG,
                ],
                "direction": ["East", "West"],
                "route": [],
            },
        ),
        # Special characters in name and direction
        (
            {
                CONF_STOP_ID: "13579",
                CONF_NAME: "Østerport",
                "departure_type": [],
                "direction": ["Syd", "Nord"],
            },
            "Østerport",
            {
                CONF_STOP_ID: 13579,
                CONF_NAME: "Østerport",
                "departure_type": [],
                "direction": ["Syd", "Nord"],
                "route": [],
            },
        ),
        # No optional fields provided (should default to empty lists)
        (
            {
                CONF_STOP_ID: "11223",
                CONF_NAME: "NoOptions",
            },
            "NoOptions",
            {
                CONF_STOP_ID: 11223,
                CONF_NAME: "NoOptions",
                "departure_type": [],
                "direction": [],
                "route": [],
            },
        ),
    ],
)
async def test_stop_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
    user_input,
    expected_title,
    expected_data,
) -> None:
    """Test adding a stop as a subentry under the main Rejseplanen entry."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    LOGGER.debug("Config Entry ID: %s", mock_config_entry.entry_id)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "stop"),
        context={"source": "user"},
    )

    LOGGER.debug("Subentry Flow Init Result: %s", result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stop"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == expected_data

    assert len(mock_config_entry.subentries) == 4
