"""Test the Ping (ICMP) config flow."""
from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.components.ping import DOMAIN
from homeassistant.components.ping.const import CONF_IMPORTED_BY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import BINARY_SENSOR_IMPORT_DATA

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("host", "expected_title"),
    (("192.618.178.1", "192.618.178.1"),),
)
@pytest.mark.usefixtures("patch_setup")
async def test_form(hass: HomeAssistant, host, expected_title) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": host,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {}
    assert result["options"] == {
        "count": 5,
        "host": host,
        "consider_home": 180,
    }


@pytest.mark.parametrize(
    ("host", "count", "expected_title"),
    (("192.618.178.1", 10, "192.618.178.1"),),
)
@pytest.mark.usefixtures("patch_setup")
async def test_options(hass: HomeAssistant, host, count, expected_title) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        version=1,
        source=config_entries.SOURCE_USER,
        data={},
        domain=DOMAIN,
        options={"count": count, "host": host, "consider_home": 180},
        title=expected_title,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "host": "10.10.10.1",
            "count": count,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "count": count,
        "host": "10.10.10.1",
        "consider_home": 180,
    }


@pytest.mark.usefixtures("patch_setup")
async def test_step_import(hass: HomeAssistant) -> None:
    """Test for import step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_IMPORTED_BY: "binary_sensor", **BINARY_SENSOR_IMPORT_DATA},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test2"
    assert result["data"] == {CONF_IMPORTED_BY: "binary_sensor"}
    assert result["options"] == {
        "host": "127.0.0.1",
        "count": 1,
        "consider_home": 240,
    }

    # test import without name
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_IMPORTED_BY: "binary_sensor", "host": "10.10.10.10", "count": 5},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "10.10.10.10"
    assert result["data"] == {CONF_IMPORTED_BY: "binary_sensor"}
    assert result["options"] == {
        "host": "10.10.10.10",
        "count": 5,
        "consider_home": 180,
    }
