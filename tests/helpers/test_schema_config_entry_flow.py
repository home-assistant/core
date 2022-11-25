"""Tests for the schema based data entry flows."""
from __future__ import annotations

from unittest.mock import patch

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from tests.common import mock_platform

TEST_DOMAIN = "test"


async def test_menu_step(hass: HomeAssistant) -> None:
    """Test menu step."""

    MENU_1 = ["option1", "option2"]
    MENU_2 = ["option3", "option4"]

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowMenuStep(MENU_1),
        "option1": SchemaFlowFormStep(vol.Schema({}), next_step=lambda _: "menu2"),
        "menu2": SchemaFlowMenuStep(MENU_2),
        "option3": SchemaFlowFormStep(vol.Schema({}), next_step="option4"),
        "option4": SchemaFlowFormStep(vol.Schema({})),
    }

    class TestConfigFlow(SchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "option1"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.MENU
        assert result["step_id"] == "menu2"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "option3"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option3"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option4"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_schema_none(hass: HomeAssistant) -> None:
    """Test SchemaFlowFormStep with schema set to None."""

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowFormStep(next_step="option1"),
        "option1": SchemaFlowFormStep(vol.Schema({}), next_step="pass"),
        "pass": SchemaFlowFormStep(next_step="option3"),
        "option3": SchemaFlowFormStep(vol.Schema({})),
    }

    class TestConfigFlow(SchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "option3"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_last_step(hass: HomeAssistant) -> None:
    """Test SchemaFlowFormStep with schema set to None."""

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowFormStep(next_step="step1"),
        "step1": SchemaFlowFormStep(vol.Schema({}), next_step="step2"),
        "step2": SchemaFlowFormStep(vol.Schema({}), next_step=lambda _: "step3"),
        "step3": SchemaFlowFormStep(vol.Schema({}), next_step=None),
    }

    class TestConfigFlow(SchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step1"
        assert result["last_step"] is False

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step2"
        assert result["last_step"] is None

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step3"
        assert result["last_step"] is True

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_next_step_function(hass: HomeAssistant) -> None:
    """Test SchemaFlowFormStep with a next_step function."""

    CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
        "user": SchemaFlowFormStep(next_step="step1"),
        "step1": SchemaFlowFormStep(vol.Schema({}), next_step=lambda _: "step2"),
        "step2": SchemaFlowFormStep(vol.Schema({}), next_step=lambda _: None),
    }

    class TestConfigFlow(SchemaConfigFlowHandler, domain=TEST_DOMAIN):
        """Handle a config or options flow for Derivative."""

        config_flow = CONFIG_FLOW

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestConfigFlow}):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step1"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "step2"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == FlowResultType.CREATE_ENTRY
