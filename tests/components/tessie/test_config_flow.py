"""Test the Tessie config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.tessie.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    ERROR_AUTH,
    ERROR_CONNECTION,
    ERROR_UNKNOWN,
    TEST_CONFIG,
    TEST_STATE_OF_ALL_VEHICLES,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == FlowResultType.FORM
    assert not result1["errors"]

    with patch(
        "homeassistant.components.tessie.config_flow.get_state_of_all_vehicles",
        return_value=TEST_STATE_OF_ALL_VEHICLES,
    ) as mock_get_state_of_all_vehicles, patch(
        "homeassistant.components.tessie.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_CONFIG,
        )
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1
        assert len(mock_get_state_of_all_vehicles.mock_calls) == 1

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Tessie"
    assert result2["data"] == TEST_CONFIG


async def test_form_invalid_access_token(hass: HomeAssistant) -> None:
    """Test invalid auth is handled."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tessie.config_flow.get_state_of_all_vehicles",
        side_effect=ERROR_AUTH,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_access_token"}


async def test_form_invalid_response(hass: HomeAssistant) -> None:
    """Test invalid auth is handled."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tessie.config_flow.get_state_of_all_vehicles",
        side_effect=ERROR_UNKNOWN,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_network_issue(hass: HomeAssistant) -> None:
    """Test network issues are handled."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tessie.config_flow.get_state_of_all_vehicles",
        side_effect=ERROR_CONNECTION,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            TEST_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
