"""Test the Ping (ICMP) config flow."""

from __future__ import annotations

import pytest

from homeassistant import config_entries
from homeassistant.components.ping import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("192.618.178.1", "192.618.178.1"),
        (" 192.618.178.1 ", "192.618.178.1"),
        (" demo.host ", "demo.host"),
    ],
)
@pytest.mark.usefixtures("patch_setup")
async def test_form(hass: HomeAssistant, host, expected) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": host,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected
    assert result["data"] == {}
    assert result["options"] == {
        "count": 5,
        "host": expected,
        "consider_home": 180,
    }


@pytest.mark.parametrize(
    ("host", "expected_host"),
    [
        ("192.618.178.1", "192.618.178.1"),
        (" 192.618.178.1 ", "192.618.178.1"),
        (" demo.host ", "demo.host"),
    ],
)
@pytest.mark.usefixtures("patch_setup")
async def test_options(hass: HomeAssistant, host: str, expected_host: str) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        version=1,
        source=config_entries.SOURCE_USER,
        data={},
        domain=DOMAIN,
        options={"count": 1, "host": "192.168.1.1", "consider_home": 180},
        title="192.168.1.1",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "host": host,
            "count": 10,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "count": 10,
        "host": expected_host,
        "consider_home": 180,
    }
