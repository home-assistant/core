"""Test the Ping (ICMP) config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ping import DOMAIN, async_setup_entry
from homeassistant.components.ping.const import CONF_IMPORTED_BY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.components.ping.const import BINARY_SENSOR_IMPORT_DATA


@pytest.mark.parametrize(
    ("platform", "extra_input"),
    (("binary_sensor", {"host": "192.618.178.1", "count": 10}),),
)
async def test_form(hass: HomeAssistant, platform, extra_input) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

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
        "name": "Router",
        "count": 10.0,
        "host": "192.618.178.1",
    }


@pytest.mark.parametrize(
    ("platform", "extra_options"),
    (("binary_sensor", {"count": 10.0, "host": "192.618.178.1"}),),
)
async def test_options(hass: HomeAssistant, platform, extra_options) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "imported_by": platform,
            "name": "Router",
            **extra_options,
        },
        title="Router",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_step_import(hass: HomeAssistant) -> None:
    """Test for import step."""

    with patch("homeassistant.components.ping.async_setup", return_value=True), patch(
        "homeassistant.components.ping.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_IMPORTED_BY: "binary_sensor", **BINARY_SENSOR_IMPORT_DATA},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "test2"
        assert result["options"] == {
            "imported_by": "binary_sensor",
            **BINARY_SENSOR_IMPORT_DATA,
        }
