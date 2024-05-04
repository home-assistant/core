"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings config flow."""

from typing import Final
from unittest.mock import MagicMock

import pytest

from homeassistant.components.dwd_weather_warnings.const import (
    CONF_REGION_DEVICE_TRACKER,
    CONF_REGION_IDENTIFIER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

DEMO_CONFIG_ENTRY_REGION: Final = {
    CONF_REGION_IDENTIFIER: "807111000",
}

DEMO_CONFIG_ENTRY_GPS: Final = {
    CONF_REGION_DEVICE_TRACKER: "device_tracker.test_gps",
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_create_entry_region(
    hass: HomeAssistant, mock_dwdwfsapi: MagicMock
) -> None:
    """Test that the full config flow works for a region identifier."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM

    mock_dwdwfsapi.__bool__.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_REGION
    )

    # Test for invalid region identifier.
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_identifier"}

    mock_dwdwfsapi.__bool__.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_REGION
    )

    # Test for successfully created entry.
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "807111000"
    assert result["data"] == {
        CONF_REGION_IDENTIFIER: "807111000",
    }


async def test_create_entry_gps(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_dwdwfsapi: MagicMock
) -> None:
    """Test that the full config flow works for a device tracker."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM

    # Test for missing registry entry error.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_GPS
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "entity_not_found"}

    # Test for missing device tracker error.
    registry_entry = entity_registry.async_get_or_create(
        "device_tracker", DOMAIN, "uuid", suggested_object_id="test_gps"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_GPS
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "entity_not_found"}

    # Test for missing attribute error.
    hass.states.async_set(
        DEMO_CONFIG_ENTRY_GPS[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LONGITUDE: "7.610263"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_GPS
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "attribute_not_found"}

    # Test for invalid provided identifier.
    hass.states.async_set(
        DEMO_CONFIG_ENTRY_GPS[CONF_REGION_DEVICE_TRACKER],
        STATE_HOME,
        {ATTR_LATITUDE: "50.180454", ATTR_LONGITUDE: "7.610263"},
    )

    mock_dwdwfsapi.__bool__.return_value = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_GPS
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_identifier"}

    # Test for successfully created entry.
    mock_dwdwfsapi.__bool__.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_GPS
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test_gps"
    assert result["data"] == {
        CONF_REGION_DEVICE_TRACKER: registry_entry.id,
    }


async def test_config_flow_already_configured(
    hass: HomeAssistant, mock_dwdwfsapi: MagicMock
) -> None:
    """Test aborting, if the warncell ID / name is already configured during the config."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_CONFIG_ENTRY_REGION.copy(),
        unique_id=DEMO_CONFIG_ENTRY_REGION[CONF_REGION_IDENTIFIER],
    )
    entry.add_to_hass(hass)

    # Start configuration of duplicate entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_CONFIG_ENTRY_REGION
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_with_errors(hass: HomeAssistant) -> None:
    """Test error scenarios during the configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM

    # Test error for empty input data.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_identifier"}

    # Test error for setting both options during configuration.
    demo_input = DEMO_CONFIG_ENTRY_REGION.copy()
    demo_input.update(DEMO_CONFIG_ENTRY_GPS.copy())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=demo_input,
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "ambiguous_identifier"}
