"""Test the Trend config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.trend import async_setup_entry
from homeassistant.components.trend.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "CPU Temperature rising", "entity_id": "sensor.cpu_temp"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM

    # test step 2 of config flow: settings of trend sensor
    with patch(
        "homeassistant.components.trend.async_setup_entry", wraps=async_setup_entry
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "invert": False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "CPU Temperature rising"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": "sensor.cpu_temp",
        "invert": False,
        "name": "CPU Temperature rising",
    }


async def test_options(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test options flow."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "min_samples": 30,
            "max_samples": 50,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "min_samples": 30,
        "max_samples": 50,
        "entity_id": "sensor.cpu_temp",
        "invert": False,
        "min_gradient": 0.0,
        "name": "My trend",
        "sample_duration": 0.0,
    }


async def test_step_import(hass: HomeAssistant) -> None:
    """Test for import step."""
    with patch(
        "homeassistant.components.trend.async_setup_entry", wraps=async_setup_entry
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "name": "test_trend_sensor",
                "entity_id": "sensor.test_state",
                "max_samples": 25,
                "min_samples": 20,
                "device_class": "battery",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test_trend_sensor"
    assert result["options"] == {
        "entity_id": "sensor.test_state",
        "max_samples": 25,
        "min_samples": 20,
        "name": "test_trend_sensor",
        "device_class": "battery",
    }


async def test_step_import_abort_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test if import step aborts when already configured."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trend.async_setup_entry", wraps=async_setup_entry
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "name": "My trend",
                "entity_id": "sensor.cpu_temp",
                "invert": False,
                "max_samples": 2.0,
                "min_gradient": 0.0,
                "sample_duration": 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
