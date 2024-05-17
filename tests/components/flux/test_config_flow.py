"""Test the Flux config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.flux.const import (
    CONF_START_CT,
    CONF_STOP_CT,
    CONF_SUNSET_CT,
    DEFAULT_SETTINGS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant):
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


@pytest.fixture(name="mock_setup_entry", autouse=True)
async def fixture_mock_setup_entry(hass: HomeAssistant):
    """Fixture for config entry."""

    with patch(
        "homeassistant.components.flux.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_configure(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"lights": []}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flux"

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options(hass: HomeAssistant) -> None:
    """Test options flow."""

    # set up stuff
    config_settings = DEFAULT_SETTINGS.copy()
    config_settings.update(
        {
            "name": "flux",
            "lights": ["light.desk", "light.lamp"],
        }
    )
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, options=config_settings)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # do something with some options
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    user_input = config_settings.copy()
    user_input[CONF_START_CT] = 800
    user_input[CONF_SUNSET_CT] = 500
    user_input[CONF_STOP_CT] = 600
    del user_input["name"]

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["data"] == config_entry.options
