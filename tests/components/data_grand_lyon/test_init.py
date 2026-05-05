"""Tests for the Data Grand Lyon integration setup."""

from types import MappingProxyType
from unittest.mock import AsyncMock

from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_STOP_ID,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_subentry_added_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that adding a subentry reloads the entry and creates new entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.c3_stop_100_next_departure_1") is not None
    assert hass.states.get("sensor.t1_stop_200_next_departure_1") is None

    initial_call_count = mock_tcl_client.get_tcl_passages.call_count

    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_LINE: "T1", CONF_STOP_ID: 200}),
            subentry_type=SUBENTRY_TYPE_STOP,
            title="T1 - Stop 200",
            unique_id="T1_200",
        ),
    )
    await hass.async_block_till_done()

    assert mock_tcl_client.get_tcl_passages.call_count > initial_call_count
    assert hass.states.get("sensor.t1_stop_200_next_departure_1") is not None
