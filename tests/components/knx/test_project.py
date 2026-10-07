"""Tests for the KNX ETS project store.

`KNXProject` keeps the parsed project behind a lazy cache: `Store.async_load`
skips its own cache for keys containing "/", so every read would otherwise
re-parse the multi-megabyte file. Whether the full project is held in memory is
left to whoever asks for it, so setup does not populate the cache.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.knx.const import KNX_MODULE_KEY
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("load_knxproj")
async def test_project_is_read_once(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """A second read must not re-parse the store file."""
    await knx.setup_integration()
    project = hass.data[KNX_MODULE_KEY].project

    assert await project.get_knxproject() is await project.get_knxproject()


@pytest.mark.usefixtures("load_knxproj")
async def test_setup_does_not_hold_the_full_project(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Setup takes what it needs and leaves the rest collectable.

    Holding the whole project would cost memory on every install that has one,
    including those that never use the LLM API or the project WebSocket command.
    """
    await knx.setup_integration()
    project = hass.data[KNX_MODULE_KEY].project

    assert project.loaded is True
    assert project._project is None


@pytest.mark.usefixtures("load_knxproj")
async def test_cache_not_resurrected_by_concurrent_load(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """A load in flight must not restore a project that was removed meanwhile."""
    await knx.setup_integration()
    project = hass.data[KNX_MODULE_KEY].project
    loading = asyncio.Event()
    original_load = project._store.async_load

    async def slow_load() -> Any:
        loading.set()
        await asyncio.sleep(0)
        return await original_load()

    with patch.object(project._store, "async_load", slow_load):
        load = hass.async_create_task(project.get_knxproject())
        await loading.wait()
        await project.remove_project_file()
    await load

    assert project._project is None


@pytest.mark.usefixtures("load_knxproj")
async def test_cache_is_refreshed_on_upload(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    project_data: dict[str, Any],
) -> None:
    """An upload must not leave a warm cache serving the old project."""
    await knx.setup_integration()
    project = hass.data[KNX_MODULE_KEY].project
    assert await project.get_knxproject() is not None

    new_data = {**project_data, "info": {**project_data["info"], "name": "Reuploaded"}}
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "knx/project_file_process", "file_id": "1234", "password": ""}
    )
    with (
        patch(
            "homeassistant.components.knx.project.process_uploaded_file"
        ) as file_upload_mock,
        patch("xknxproject.XKNXProj.parse", return_value=new_data),
    ):
        file_upload_mock.return_value.__enter__.return_value = ""
        res = await client.receive_json()

    assert res["success"], res
    knxproject = await project.get_knxproject()
    assert knxproject["info"]["name"] == "Reuploaded"
