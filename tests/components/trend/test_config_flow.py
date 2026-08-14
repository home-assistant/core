"""Test the Trend config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.trend import async_setup_entry
from homeassistant.components.trend.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("name", "entity_id"),
    [
        ("CPU Temperature rising", "sensor.cpu_temp"),
        ("People arrived rising", "counter.people"),
    ],
    ids=["sensor", "counter"],
)
async def test_form(hass: HomeAssistant, name: str, entity_id: str) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": name, "entity_id": entity_id},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == name
    assert result["data"] == {}
    assert result["options"] == {
        "entity_id": entity_id,
        "invert": False,
        "name": name,
    }


async def test_options(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test options flow."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "min_samples": 30,
            "max_samples": 50,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "min_samples": 30,
        "max_samples": 50,
        "entity_id": "sensor.cpu_temp",
        "invert": False,
        "min_gradient": 0.0,
        "name": "My trend",
        "sample_duration": 0.0,
    }
