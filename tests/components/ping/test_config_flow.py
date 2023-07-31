"""Test the Ping (ICMP) config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ping import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

BINARY_SENSOR_IMPORT_DATA = {
    "name": "test2",
    "host": "127.0.0.1",
    "count": 1,
}


@pytest.mark.parametrize(
    ("platform_type", "extra_input"),
    (("binary_sensor", {"host": "192.618.178.1", "count": 10}),),
)
async def test_form(hass: HomeAssistant, platform_type, extra_input) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": platform_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == platform_type

    with patch(
        "homeassistant.components.group.async_setup_entry", wraps=async_setup_entry
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Router",
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Router"
    assert result["data"] == {}
    assert result["options"] == {
        "platform_type": platform_type,
        "name": "Router",
        "count": 10.0,
        "host": "192.618.178.1",
    }


async def test_step_import(hass: HomeAssistant) -> None:
    """Test for import step."""

    with patch("homeassistant.components.ping.async_setup", return_value=True), patch(
        "homeassistant.components.ping.async_setup_entry", return_value=True
    ):
        data = BINARY_SENSOR_IMPORT_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "test2"
        assert result["options"] == {
            "platform_type": "binary_sensor",
            **BINARY_SENSOR_IMPORT_DATA,
        }

        data = {"count": 10, "ip": "127.0.0.1"}
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )
        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.ABORT
