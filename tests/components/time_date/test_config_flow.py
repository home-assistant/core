"""Test the Time & Date config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.time_date.const import CONF_DISPLAY_OPTIONS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import WebSocketGenerator

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the forms."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_options": "time"},
    )
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_user_flow_does_not_allow_beat(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the forms."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with pytest.raises(vol.Invalid):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"display_options": ["beat"]},
        )


async def test_single_instance(hass: HomeAssistant) -> None:
    """Test we get the forms."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={}, options={CONF_DISPLAY_OPTIONS: "time"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_options": "time"},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_timezone_not_set(hass: HomeAssistant) -> None:
    """Test time zone not set."""
    hass.config.time_zone = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"display_options": "time"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "timezone_not_exist"}


async def test_config_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)
    freezer.move_to("2024-01-02 20:14:11.672")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None
    assert result["preview"] == "time_date"

    await client.send_json_auto_id(
        {
            "type": "time_date/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"display_options": "time"},
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "Time", "icon": "mdi:clock"},
        "state": "12:14",
    }

    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "Time", "icon": "mdi:clock"},
        "state": "12:15",
    }
    assert len(hass.states.async_all()) == 0
