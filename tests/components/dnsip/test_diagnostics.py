"""Tests for the DNS IP diagnostics."""

from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.dnsip.const import (
    CONF_HOSTNAME,
    CONF_IPV4,
    CONF_IPV6,
    CONF_PORT_IPV6,
    CONF_RESOLVER,
    CONF_RESOLVER_IPV6,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from . import RetrieveDNS


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_HOSTNAME: "home-assistant.io",
            CONF_NAME: "home-assistant.io",
            CONF_IPV4: True,
            CONF_IPV6: True,
        },
        options={
            CONF_RESOLVER: "208.67.222.222",
            CONF_RESOLVER_IPV6: "2620:119:53::53",
            CONF_PORT: 53,
            CONF_PORT_IPV6: 53,
        },
        entry_id="1",
        title="home-assistant.io",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dnsip.aiodns.DNSResolver",
        side_effect=[RetrieveDNS(), RetrieveDNS()],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
