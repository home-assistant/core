"""Tests for the Cloudflare integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pycfdns

from homeassistant.components.cloudflare.const import CONF_RECORDS, DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_API_TOKEN: "mock-api-token",
    CONF_ZONE: "mock.com",
    CONF_RECORDS: ["ha.mock.com", "homeassistant.mock.com"],
}

ENTRY_OPTIONS = {}

USER_INPUT = {
    CONF_API_TOKEN: "mock-api-token",
}

USER_INPUT_ZONE = {CONF_ZONE: "mock.com"}

USER_INPUT_RECORDS = {CONF_RECORDS: ["ha.mock.com", "homeassistant.mock.com"]}

MOCK_ZONE: pycfdns.ZoneModel = {"name": "mock.com", "id": "mock-zone-id"}
MOCK_ZONE_RECORDS: list[pycfdns.RecordModel] = [
    {
        "id": "zone-record-id",
        "type": "A",
        "name": "ha.mock.com",
        "proxied": True,
        "content": "127.0.0.1",
    },
    {
        "id": "zone-record-id-2",
        "type": "A",
        "name": "homeassistant.mock.com",
        "proxied": True,
        "content": "127.0.0.1",
    },
    {
        "id": "zone-record-id-3",
        "type": "A",
        "name": "mock.com",
        "proxied": True,
        "content": "127.0.0.1",
    },
    {
        "id": "zone-record-id-4",
        "type": "AAAA",
        "name": "ha.mock.com",
        "proxied": True,
        "content": "::1",
    },
    {
        "id": "zone-record-id-5",
        "type": "AAAA",
        "name": "homeassistant.mock.com",
        "proxied": True,
        "content": "::1",
    },
]


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict[str, Any] | UndefinedType = UNDEFINED,
    options: dict[str, Any] | UndefinedType = UNDEFINED,
    unique_id: str = MOCK_ZONE["name"],
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Cloudflare integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_CONFIG if data is UNDEFINED else data,
        options=ENTRY_OPTIONS if options is UNDEFINED else options,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def get_mock_client() -> Mock:
    """Return a Mock of pycfdns.Client."""
    client = Mock()

    client.list_zones = AsyncMock(return_value=[MOCK_ZONE])

    def list_dns_records(zone_id, type=None):
        if type == "A":
            return [r for r in MOCK_ZONE_RECORDS if r["type"] == "A"]
        if type == "AAAA":
            return [r for r in MOCK_ZONE_RECORDS if r["type"] == "AAAA"]
        return MOCK_ZONE_RECORDS

    client.list_dns_records = AsyncMock(side_effect=list_dns_records)
    client.update_dns_record = AsyncMock(return_value=None)

    return client


def patch_async_setup_entry() -> AsyncMock:
    """Patch the async_setup_entry method and return a mock."""
    return patch(
        "homeassistant.components.cloudflare.async_setup_entry",
        return_value=True,
    )
