"""Test the Transport NSW config flow."""

from unittest.mock import patch

from homeassistant.components.transport_nsw.const import (
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USER_DATA = {
    CONF_API_KEY: "test_api_key",
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
}

EXPECTED_CONFIG_DATA = {
    CONF_API_KEY: "test_api_key",
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
    CONF_ROUTE: "",
    CONF_DESTINATION: "",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        return_value={"title": "Test Stop (test_stop_id)"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Stop (test_stop_id)"
    assert result2["data"] == EXPECTED_CONFIG_DATA


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_multiple_stops_same_id(hass: HomeAssistant) -> None:
    """Test we can configure multiple sensors for the same stop_id."""
    # First entry
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
    )
    entry1.add_to_hass(hass)

    # Second entry with same stop_id but different name
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    second_data = {**MOCK_USER_DATA, CONF_NAME: "Test Stop 2"}
    expected_second_data = {**EXPECTED_CONFIG_DATA, CONF_NAME: "Test Stop 2"}

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        return_value={"title": "Test Stop 2 (test_stop_id)"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            second_data,
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Stop 2 (test_stop_id)"
    assert result2["data"] == expected_second_data


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
        unique_id="test_stop_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Updated Test Stop",
            CONF_ROUTE: "test_route",
            CONF_DESTINATION: "test_destination",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_NAME: "Updated Test Stop",
        CONF_ROUTE: "test_route",
        CONF_DESTINATION: "test_destination",
    }
