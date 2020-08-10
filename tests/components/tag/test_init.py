"""Tests for the tag component."""
import logging

import pytest

from homeassistant.components.tag import DOMAIN, async_scan_tag
from homeassistant.setup import async_setup_component

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def storage_setup(hass, hass_storage):
    """Storage setup."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": [{"id": "test tag"}]},
            }
        else:
            hass_storage[DOMAIN] = items
        config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_ws_list(hass, hass_ws_client, storage_setup):
    """Test listing tags via WS."""
    assert await storage_setup()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert "test tag" in result


async def test_tag_scanned(hass, hass_ws_client, storage_setup):
    """Test scanning tags."""
    assert await storage_setup()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert "test tag" in result

    await async_scan_tag(hass, "new tag", "some_scanner")
    await client.send_json({"id": 7, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 2
    assert "test tag" in result
    assert "new tag" in result
    assert result["new tag"]["last_scanned"] is not None
