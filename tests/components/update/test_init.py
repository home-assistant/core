"""Tests for the Version integration init."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock

from homeassistant.components.update import (
    DOMAIN,
    UpdateDescription,
    UpdateRegistration,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


async def setup_mock_domain(
    hass: HomeAssistant,
    get_updates: Callable[[HomeAssistant], Awaitable[list[UpdateDescription]]]
    | None = None,
    update_callback: Callable[[HomeAssistant, UpdateDescription, dict], Awaitable[bool]]
    | None = None,
) -> None:
    """Set up a mock domain."""

    async def mock_get_updates(hass: HomeAssistant) -> list[UpdateDescription]:
        return [
            UpdateDescription(
                identifier="lorem_ipsum",
                name="Lorem Ipsum",
                current_version="1.0.0",
                available_version="1.0.1",
                update_callback=update_callback or AsyncMock(),
            )
        ]

    @callback
    def _mock_async_register(registration: UpdateRegistration) -> None:
        registration.async_register(get_updates or mock_get_updates)

    mock_platform(
        hass,
        "some_domain.update",
        Mock(
            async_register=_mock_async_register,
        ),
    )

    assert await async_setup_component(hass, "some_domain", {})


async def gather_update_info(hass, hass_ws_client) -> list[dict]:
    """Gather all info."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "update/info"})
    resp = await client.receive_json()
    return resp["result"]


async def test_update_updates(hass, hass_ws_client):
    """Test getting updates."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1
    data = data[0] == {
        "domain": "some_domain",
        "identifier": "lorem_ipsum",
        "name": "Lorem Ipsum",
        "current_version": "1.0.0",
        "available_version": "1.0.1",
        "changelog_url": None,
        "icon_url": None,
    }


async def test_update_updates_with_timeout_error(hass, hass_ws_client):
    """Test timeout while getting updates."""

    async def mock_get_updates(hass: HomeAssistant) -> list[UpdateDescription]:
        raise asyncio.TimeoutError()

    await setup_mock_domain(hass, get_updates=mock_get_updates)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 0


async def test_update_updates_with_exception(hass, hass_ws_client):
    """Test exception while getting updates."""

    async def mock_get_updates(hass: HomeAssistant) -> list[UpdateDescription]:
        raise Exception()

    await setup_mock_domain(hass, get_updates=mock_get_updates)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 0


async def test_update_update(hass, hass_ws_client):
    """Test performing an update."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1
    update = data[0]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/update",
            "domain": update["domain"],
            "identifier": update["identifier"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    assert resp["result"] == []


async def test_skip_update(hass, hass_ws_client):
    """Test skipping updates."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1
    update = data[0]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/skip",
            "domain": update["domain"],
            "identifier": update["identifier"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    assert resp["result"] == []

    data = await gather_update_info(hass, hass_ws_client)
    assert len(data) == 0


async def test_skip_non_existing_update(hass, hass_ws_client):
    """Test skipping non-existing updates."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/skip",
            "domain": "non_existing",
            "identifier": "non_existing",
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    data = await gather_update_info(hass, hass_ws_client)
    assert len(data) == 1


async def test_update_update_non_existing(hass, hass_ws_client):
    """Test that we fail when trying to update something that does not exist."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1
    update = data[0]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/update",
            "domain": update["domain"],
            "identifier": "does_not_exist",
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "not_found"


async def test_update_update_failed(hass, hass_ws_client):
    """Test that we correctly handle failed updates."""

    async def mock_update_callback(
        hass: HomeAssistant, data: UpdateDescription, **kwargs
    ) -> bool:
        return False

    await setup_mock_domain(hass, update_callback=mock_update_callback)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1
    update = data[0]

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/update",
            "domain": update["domain"],
            "identifier": update["identifier"],
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "update_failed"
