"""Tests for the Junker config flow."""

from unittest.mock import Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.junker.const import (
    CONF_AREA_ID,
    CONF_MUNICIPALITY,
    CONF_TITLE,
    CONF_WASTE_TYPES,
    DOMAIN,
)
from homeassistant.components.junker.junker_api import Area, AreaRequired, JunkerError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from .conftest import TEST_MUNICIPALITY

NAMES = {"Organic waste": "Kitchen", "Paper": "Cardboard"}


async def _complete(hass: HomeAssistant, flow_id: str) -> FlowResult:
    """Fill the settings and names steps."""
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input={CONF_TITLE: "Home", CONF_WASTE_TYPES: list(NAMES)}
    )
    for name in NAMES.values():
        assert result["step_id"] == "names"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TITLE: name}
        )
    return result


@pytest.mark.usefixtures("mock_junker_client")
async def test_create_entry_without_area(hass: HomeAssistant) -> None:
    """Test creating an entry for a municipality without areas."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    assert result["step_id"] == "settings"

    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["result"].unique_id == f"{TEST_MUNICIPALITY.casefold()}:all"
    assert result["data"] == {CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    assert result["options"] == {CONF_WASTE_TYPES: NAMES}


@pytest.mark.usefixtures("mock_junker_client")
async def test_create_entry_with_area(hass: HomeAssistant, client: Mock) -> None:
    """Test creating an entry after selecting a Junker area."""
    client.async_get_collections.side_effect = [
        AreaRequired([Area(1, "Central area")]),
        client.async_get_collections.return_value,
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "area"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AREA_ID: "1"}
    )
    assert result["step_id"] == "settings"

    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MUNICIPALITY: TEST_MUNICIPALITY,
        CONF_AREA_ID: "1",
    }
    assert result["options"] == {CONF_WASTE_TYPES: NAMES}


@pytest.mark.usefixtures("mock_junker_client")
async def test_duplicate_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a configured municipality cannot be added twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test changing the name and the waste types."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_TITLE: "Home", CONF_WASTE_TYPES: ["Paper"]},
    )
    assert result["step_id"] == "names"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TITLE: "Cardboard"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.title == "Home"
    assert init_integration.options == {CONF_WASTE_TYPES: {"Paper": "Cardboard"}}


@pytest.mark.usefixtures("mock_junker_client")
async def test_invalid_municipality(hass: HomeAssistant, client: Mock) -> None:
    """Test an invalid municipality shows an error."""
    client.async_get_collections.side_effect = JunkerError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_municipality"}
    client.async_get_collections.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_junker_client")
async def test_unexpected_municipality_error(hass: HomeAssistant, client: Mock) -> None:
    """Test an unexpected municipality validation error."""
    client.async_get_collections.side_effect = RuntimeError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    client.async_get_collections.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_junker_client")
async def test_invalid_area(hass: HomeAssistant, client: Mock) -> None:
    """Test an invalid area shows an error."""
    client.async_get_collections.side_effect = [
        AreaRequired([Area(1, "Central area")]),
        JunkerError,
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AREA_ID: "1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_area"}
    client.async_get_collections.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AREA_ID: "1"}
    )
    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_junker_client")
async def test_unexpected_area_error(hass: HomeAssistant, client: Mock) -> None:
    """Test an unexpected area validation error."""
    client.async_get_collections.side_effect = [
        AreaRequired([Area(1, "Central area")]),
        RuntimeError,
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_MUNICIPALITY: TEST_MUNICIPALITY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AREA_ID: "1"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    client.async_get_collections.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_AREA_ID: "1"}
    )
    result = await _complete(hass, result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
