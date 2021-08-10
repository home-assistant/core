"""Test the Switcher config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.switcher_kis.const import DATA_DISCOVERY, DOMAIN
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .consts import DUMMY_PLUG_DEVICE, DUMMY_WATER_HEATER_DEVICE

from tests.common import MockConfigEntry


async def test_import(hass):
    """Test import step."""
    with patch(
        "homeassistant.components.switcher_kis.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Switcher"
    assert result["data"] == {}


@pytest.mark.parametrize(
    "mock_bridge",
    [
        [
            DUMMY_PLUG_DEVICE,
            DUMMY_WATER_HEATER_DEVICE,
            # Make sure we don't detect the same device twice
            DUMMY_WATER_HEATER_DEVICE,
        ]
    ],
    indirect=True,
)
async def test_user_setup(hass, mock_bridge):
    """Test we can finish a config flow."""
    with patch("homeassistant.components.switcher_kis.utils.asyncio.sleep"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert mock_bridge.is_running is False
    assert len(hass.data[DOMAIN][DATA_DISCOVERY].result()) == 2

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.switcher_kis.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Switcher"
    assert result2["result"].data == {}


async def test_user_setup_abort_no_devices_found(hass, mock_bridge):
    """Test we abort a config flow if no devices found."""
    with patch("homeassistant.components.switcher_kis.utils.asyncio.sleep"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert mock_bridge.is_running is False
    assert len(hass.data[DOMAIN][DATA_DISCOVERY].result()) == 0

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    "source",
    [
        config_entries.SOURCE_IMPORT,
        config_entries.SOURCE_USER,
    ],
)
async def test_single_instance(hass, source):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"
