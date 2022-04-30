"""Test the Fjäråskupan config flow."""
from __future__ import annotations

from unittest.mock import patch

from bleak.backends.device import BLEDevice
from pytest import fixture

from homeassistant import config_entries
from homeassistant.components.fjaraskupan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


@fixture(name="mock_setup_entry", autouse=True)
async def fixture_mock_setup_entry(hass):
    """Fixture for config entry."""

    with patch(
        "homeassistant.components.fjaraskupan.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_configure(hass: HomeAssistant, mock_setup_entry) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Fjäråskupan"
    assert result["data"] == {}

    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_scan_no_devices(hass: HomeAssistant, scanner: list[BLEDevice]) -> None:
    """Test we get the form."""
    scanner.clear()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "no_devices_found"
