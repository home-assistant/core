"""Tests for the Cloudflare integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pycfdns

from homeassistant.components.cloudflare.const import CONF_RECORDS, DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_ZONE

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
]


async def init_integration(
    hass,
    *,
    data: dict = ENTRY_CONFIG,
    options: dict = ENTRY_OPTIONS,
    unique_id: str = MOCK_ZONE["name"],
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Cloudflare integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options=options,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def _get_mock_client(zone: str = MOCK_ZONE, records: list = MOCK_ZONE_RECORDS):
    client: pycfdns.Client = AsyncMock()

    client.list_zones = AsyncMock(return_value=[zone])
    client.list_dns_records = AsyncMock(return_value=records)
    client.update_dns_record = AsyncMock(return_value=None)

    return client


def _patch_async_setup_entry(return_value=True):
    return patch(
        "homeassistant.components.cloudflare.async_setup_entry",
        return_value=return_value,
    )
