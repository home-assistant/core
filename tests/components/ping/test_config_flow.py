"""Test the Ping (ICMP) config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ping import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("host", "count", "expected_title"),
    (("192.618.178.1", 10, "192.618.178.1"),),
)
async def test_form(hass: HomeAssistant, host, count, expected_title) -> None:
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
                "host": host,
                "count": count,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_title
    assert result["data"] == {}
    assert result["options"] == {
        "count": count,
        "host": host,
    }


@pytest.mark.parametrize(
    ("host", "count", "expected_title"),
    (("192.618.178.1", 10, "192.618.178.1"),),
)
async def test_options(hass: HomeAssistant, host, count, expected_title) -> None:
    """Test options flow."""

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={"count": count, "host": host},
        title=expected_title,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
