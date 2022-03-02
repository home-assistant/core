"""Tests for the Update integration init."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import Mock, patch

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.update import DOMAIN, UpdateDescription, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


async def setup_mock_domain(
    hass: HomeAssistant,
    async_list_updates: Callable[[HomeAssistant], Awaitable[list[UpdateDescription]]]
    | None = None,
    async_perform_update: Callable[[HomeAssistant, str, str], Awaitable[bool]]
    | None = None,
) -> None:
    """Set up a mock domain."""

    async def _mock_async_list_updates(hass: HomeAssistant) -> list[UpdateDescription]:
        return [
            UpdateDescription(
                identifier="lorem_ipsum",
                name="Lorem Ipsum",
                current_version="1.0.0",
                available_version="1.0.1",
            )
        ]

    async def _mock_async_perform_update(
        hass: HomeAssistant,
        identifier: str,
        version: str,
        **kwargs: Any,
    ) -> bool:
        return True

    mock_platform(
        hass,
        "some_domain.update",
        Mock(
            async_list_updates=async_list_updates or _mock_async_list_updates,
            async_perform_update=async_perform_update or _mock_async_perform_update,
        ),
    )

    assert await async_setup_component(hass, "some_domain", {})


async def gather_update_info(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> list[dict]:
    """Gather all info."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "update/info"})
    resp = await client.receive_json()
    return resp["result"]


async def test_update_updates(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test getting updates."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.components.update.storage.Store.async_load",
        return_value={"skipped": []},
    ):
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


async def test_update_updates_with_timeout_error(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test timeout while getting updates."""

    async def mock_async_list_updates(hass: HomeAssistant) -> list[UpdateDescription]:
        raise asyncio.TimeoutError()

    await setup_mock_domain(hass, async_list_updates=mock_async_list_updates)

    assert await async_setup_component(hass, DOMAIN, {})

    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 0


async def test_update_updates_with_exception(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test exception while getting updates."""

    async def mock_async_list_updates(hass: HomeAssistant) -> list[UpdateDescription]:
        raise Exception()

    await setup_mock_domain(hass, async_list_updates=mock_async_list_updates)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 0


async def test_update_update(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
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
            "version": update["available_version"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]


async def test_skip_update(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
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
            "version": update["available_version"],
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    data = await gather_update_info(hass, hass_ws_client)
    assert len(data) == 0


async def test_skip_non_existing_update(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
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
            "version": "non_existing",
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]

    data = await gather_update_info(hass, hass_ws_client)
    assert len(data) == 1


async def test_update_update_non_existing(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test that we fail when trying to update something that does not exist."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    data = await gather_update_info(hass, hass_ws_client)

    assert len(data) == 1

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/update",
            "domain": "does_not_exist",
            "identifier": "does_not_exist",
            "version": "non_existing",
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "not_found"


async def test_update_update_failed(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test that we correctly handle failed updates."""

    async def mock_async_perform_update(
        hass: HomeAssistant,
        identifier: str,
        version: str,
        **kwargs,
    ) -> bool:
        raise UpdateFailed("Test update failed")

    await setup_mock_domain(hass, async_perform_update=mock_async_perform_update)

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
            "version": update["available_version"],
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "update_failed"
    assert (
        resp["error"]["message"]
        == f"Update of {update['domain']}/{update['identifier']} to version {update['available_version']} failed: Test update failed"
    )


async def test_update_update_failed_generic(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we correctly handle failed updates."""

    async def mock_async_perform_update(
        hass: HomeAssistant,
        identifier: str,
        version: str,
        **kwargs,
    ) -> bool:
        raise TypeError("Test update failed")

    await setup_mock_domain(hass, async_perform_update=mock_async_perform_update)

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
            "version": update["available_version"],
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "update_failed"
    assert (
        resp["error"]["message"]
        == f"Update of {update['domain']}/{update['identifier']} to version {update['available_version']} failed: Test update failed"
    )
    assert (
        f"Update of {update['domain']}/{update['identifier']} to version {update['available_version']}"
        in caplog.text
    )


async def test_update_before_info(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test that we fail when trying to update something that does not exist."""
    await setup_mock_domain(hass)

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "update/update",
            "domain": "does_not_exist",
            "identifier": "does_not_exist",
            "version": "non_existing",
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "not_found"
