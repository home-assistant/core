"""Tests for Deutscher Wetterdienst (DWD) Weather Warnings config flow."""

from typing import Final
from unittest.mock import patch

import pytest

from homeassistant.components.dwd_weather_warnings.const import (
    ADVANCE_WARNING_SENSOR,
    CONF_REGION_IDENTIFIER,
    CONF_REGION_NAME,
    CURRENT_WARNING_SENSOR,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DEMO_CONFIG_ENTRY: Final = {
    CONF_REGION_IDENTIFIER: "807111000",
}

DEMO_YAML_CONFIGURATION: Final = {
    CONF_NAME: "Unit Test",
    CONF_REGION_NAME: "807111000",
    CONF_MONITORED_CONDITIONS: [CURRENT_WARNING_SENSOR, ADVANCE_WARNING_SENSOR],
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the full config flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.dwd_weather_warnings.config_flow.DwdWeatherWarningsAPI",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_CONFIG_ENTRY
        )

    # Test for invalid region identifier.
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_identifier"}

    with patch(
        "homeassistant.components.dwd_weather_warnings.config_flow.DwdWeatherWarningsAPI",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_CONFIG_ENTRY
        )

    # Test for successfully created entry.
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "807111000"
    assert result["data"] == {
        CONF_REGION_IDENTIFIER: "807111000",
    }


async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test aborting, if the warncell ID / name is already configured during the config."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEMO_CONFIG_ENTRY.copy(),
        unique_id=DEMO_CONFIG_ENTRY[CONF_REGION_IDENTIFIER],
    )
    entry.add_to_hass(hass)

    # Start configuration of duplicate entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.dwd_weather_warnings.config_flow.DwdWeatherWarningsAPI",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_CONFIG_ENTRY
        )

    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
