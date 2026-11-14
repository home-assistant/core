"""Tests for the assist_satellite LLM tools platform."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    floor_registry as fr,
    intent,
    llm,
)
from homeassistant.setup import async_setup_component

from .conftest import TEST_DOMAIN, MockAssistSatellite

from tests.components.tts.common import MockResultStream

TOOL_NAME = "assist_satellite__broadcast"


@pytest.fixture(autouse=True)
async def init_integrations(hass: HomeAssistant, init_components: ConfigEntry) -> None:
    """Set up the integrations and the test satellites."""
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "llm", {})


@pytest.fixture
async def mock_tts_engine(hass: HomeAssistant):
    """Mock the TTS engine that turns the message into audio."""
    assert await async_setup_component(hass, "tts", {})
    with (
        patch(
            "homeassistant.components.tts.async_resolve_engine",
            return_value="tts.cloud",
        ),
        patch(
            "homeassistant.components.tts.generate_media_source_id",
            return_value="media-source://bla",
        ),
        patch(
            "homeassistant.components.tts.async_create_stream",
            return_value=MockResultStream(hass, "wav", b""),
        ),
    ):
        yield


def _llm_context(device_id: str | None = None) -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=device_id,
    )


async def _async_broadcast(
    hass: HomeAssistant, tool_args: dict[str, Any], device_id: str | None
) -> llm.ToolResult:
    """Call the broadcast tool through the Assist API."""
    api = await llm.async_get_api(hass, "assist", _llm_context(device_id))
    result = await api.async_call_tool(
        llm.ToolInput(tool_name=TOOL_NAME, tool_args=tool_args)
    )
    # The tool does not wait for the announcements to finish.
    await hass.async_block_till_done()
    return result


async def test_broadcast_tool_offered(hass: HomeAssistant) -> None:
    """Test the broadcast tool is offered to the Assist API."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    tools = {tool.name: tool for tool in result.tools}

    tool = tools[TOOL_NAME]
    assert tool.title == "Broadcast message"
    assert tool.integration == "assist_satellite"
    # A broadcast announces again on every call and takes nothing away.
    assert tool.annotations == llm.ToolAnnotations(destructive=False, open_world=False)


@pytest.mark.usefixtures("mock_tts_engine")
async def test_broadcast_whole_home(
    hass: HomeAssistant,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    entity_no_features: MockAssistSatellite,
) -> None:
    """Test a broadcast to the whole home skips the satellite that asked."""
    result = await _async_broadcast(
        hass, {"message": "Hello", "area": ""}, entity.device_entry.id
    )

    assert result == llm.ToolResult(data={"satellites": ["Test Entity 2"]})
    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 1
    assert entity2.announcements[0].message == "Hello"
    assert len(entity_no_features.announcements) == 0


@pytest.mark.parametrize(
    "target", [{"area": "kitchen"}, {"floor": "Upstairs"}], ids=["area", "floor"]
)
@pytest.mark.usefixtures("mock_tts_engine")
async def test_broadcast_area_or_floor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    floor_registry: fr.FloorRegistry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    target: dict[str, str],
) -> None:
    """Test a broadcast to an area or floor only reaches the satellites there."""
    floor = floor_registry.async_create("Upstairs")
    kitchen = area_registry.async_create("Kitchen", floor_id=floor.floor_id)
    living_room = area_registry.async_create("Living room")
    device_registry.async_update_device(entity.device_entry.id, area_id=living_room.id)
    device_registry.async_update_device(entity2.device_entry.id, area_id=kitchen.id)

    result = await _async_broadcast(hass, {"message": "Hello", **target}, None)

    assert result == llm.ToolResult(data={"satellites": ["Test Entity 2"]})
    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 1


@pytest.mark.usefixtures("mock_tts_engine")
async def test_broadcast_area_skips_asking_satellite(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity: MockAssistSatellite,
) -> None:
    """Test a broadcast to an area skips the satellite that asked."""
    kitchen = area_registry.async_create("Kitchen")
    device_registry.async_update_device(entity.device_entry.id, area_id=kitchen.id)

    with pytest.raises(intent.MatchFailedError, match="No entities were in the area"):
        await _async_broadcast(
            hass, {"message": "Hello", "area": "Kitchen"}, entity.device_entry.id
        )

    assert len(entity.announcements) == 0


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ({"area": "Garage"}, "The area does not exist"),
        ({"area": "Living room"}, "No entities were in the area"),
        ({"floor": "Basement"}, "The floor does not exist"),
    ],
    ids=["unknown_area", "empty_area", "unknown_floor"],
)
@pytest.mark.usefixtures("mock_tts_engine")
async def test_broadcast_no_satellite(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity: MockAssistSatellite,
    entity2: MockAssistSatellite,
    target: dict[str, str],
    error: str,
) -> None:
    """Test a broadcast to an area or floor without a satellite fails."""
    area_registry.async_create("Living room")

    with pytest.raises(intent.MatchFailedError, match=error):
        await _async_broadcast(hass, {"message": "Hello", **target}, None)

    assert len(entity.announcements) == 0
    assert len(entity2.announcements) == 0


@pytest.mark.usefixtures("mock_tts_engine")
async def test_broadcast_area_all_satellites_excluded(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity: MockAssistSatellite,
) -> None:
    """Test a broadcast to an area does not reach excluded satellites."""
    kitchen = area_registry.async_create("Kitchen")
    device_registry.async_update_device(entity.device_entry.id, area_id=kitchen.id)

    with (
        patch(
            "homeassistant.components.assist_satellite.intent.EXCLUDED_DOMAINS",
            new={TEST_DOMAIN},
        ),
        pytest.raises(intent.MatchFailedError, match="No entities were in the area"),
    ):
        await _async_broadcast(hass, {"message": "Hello", "area": "Kitchen"}, None)

    assert len(entity.announcements) == 0
