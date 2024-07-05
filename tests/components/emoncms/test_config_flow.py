"""Test emoncms config flow."""

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.components.emoncms.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigFlowResult
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import (
    FAILURE_MESSAGE,
    FINAL,
    FINAL_2,
    IMPORTED_YAML,
    USER_INPUT,
    USER_INPUT_2,
    YAML_INPUT,
)

from tests.common import MockConfigEntry


async def flow_import(hass: HomeAssistant, yaml: dict[str, Any]) -> ConfigFlowResult:
    """Import of a yaml config."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=yaml,
    )


async def test_flow_import(
    hass: HomeAssistant,
    emoncms_client: AsyncMock,
) -> None:
    """YAML import - success test."""
    result = await flow_import(hass, YAML_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == YAML_INPUT[CONF_ID]
    assert result["data"] == IMPORTED_YAML


async def test_flow_import_failure(
    hass: HomeAssistant,
    emoncms_client_failure: AsyncMock,
) -> None:
    """Import of a YAML config - failure test."""
    result = await flow_import(hass, YAML_INPUT)
    assert result["type"] == FlowResultType.ABORT


async def options_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    user_input: dict[str, Any],
    final: dict[str, Any],
) -> None:
    """Options flow generic success test."""
    await setup_integration(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=user_input,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == final


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client: AsyncMock,
    config_entry: MockConfigEntry,
    config_entry_2: MockConfigEntry,
    config_entry_3: MockConfigEntry,
) -> None:
    """Options flow - success test."""
    await options_flow(hass, config_entry, USER_INPUT, FINAL)
    await options_flow(hass, config_entry_2, USER_INPUT_2, FINAL_2)
    await options_flow(hass, config_entry_3, USER_INPUT_2, FINAL_2)


async def test_options_flow_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    emoncms_client_failure: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Options flow - test failure."""
    await setup_integration(hass, config_entry)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["errors"]["base"] == FAILURE_MESSAGE
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
