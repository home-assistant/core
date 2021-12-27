"""Test the dnsip config flow."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.dnsip.const import (
    CONF_HOSTNAME,
    CONF_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DOMAIN,
)
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.dnsip.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOSTNAME: "home-assistant.io",
                CONF_RESOLVER: "8.8.8.8",
                CONF_IPV6: False,
                CONF_RESOLVER_IPV6: "2620:0:ccc::2",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "home-assistant.io"
    assert result2["data"] == {
        "hostname": "home-assistant.io",
        "resolver": "8.8.8.8",
        "ipv6": False,
        "resolver_ipv6": "2620:0:ccc::2",
        "name": "home-assistant.io",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "p_input,p_output",
    [
        (
            {
                "hostname": "home-assistant.io",
                "resolver": "8.8.8.8",
                "ipv6": False,
                "resolver_ipv6": "",
            },
            {
                "hostname": "home-assistant.io",
                "resolver": "8.8.8.8",
                "ipv6": False,
                "resolver_ipv6": "",
                "name": "home-assistant.io",
            },
        ),
        (
            {},
            {
                "hostname": "myip.opendns.com",
                "resolver": "208.67.222.222",
                "ipv6": False,
                "resolver_ipv6": "2620:0:ccc::2",
                "name": "myip",
            },
        ),
    ],
)
async def test_import_flow_success(
    hass: HomeAssistant, p_input: dict[str, str], p_output: dict[str, str]
) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.dnsip.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=p_input,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == p_output["name"]
    assert result2["data"] == p_output
    assert len(mock_setup_entry.mock_calls) == 1
