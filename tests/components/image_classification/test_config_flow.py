"""Tests for the Image classification config and options flows."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components.image_classification.const import (
    CONF_AI_TASK_ENTITY_ID,
    CONF_LEFT,
    CONF_TOP,
    DOMAIN,
)
from homeassistant.components.image_classification.frame_source import prepare_frame
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import entity_registry as er

from . import (
    CAMERA,
    CLASSIFIER,
    REGION,
    USER_INPUT,
    FakeCamera,
    FakeClassifier,
    frame_files,
    render_frame,
    setup_integration,
    stored_frames,
    teach_both,
)

PREVIEW_PREFIX = f"/api/{DOMAIN}/preview/"


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    return result["flow_id"]


async def _open(hass: HomeAssistant, entry: MockConfigEntry, step: str) -> str:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )
    assert result["step_id"] == step
    return result["flow_id"]


def _suggested(result: FlowResult, field: str) -> Any:
    """Return the value a form fills in for a field."""
    key = next(key for key in result["data_schema"].schema if key == field)
    return key.description["suggested_value"]


@pytest.mark.usefixtures("camera")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Pick a camera and an AI Task entity, set the region, confirm it."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["step_id"] == "region"
    assert result["description_placeholders"]["preview"].startswith(PREVIEW_PREFIX)

    result = await hass.config_entries.flow.async_configure(flow_id, REGION)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "region_confirm"
    assert result["description_placeholders"]["preview"].startswith(PREVIEW_PREFIX)

    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage"
    assert result["data"] == {}
    assert result["options"] == {
        CONF_ENTITY_ID: CAMERA,
        CONF_DEVICE_CLASS: "occupancy",
        CONF_AI_TASK_ENTITY_ID: CLASSIFIER,
        CONF_REGION: REGION,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("preferred", "registered", "expected"),
    [
        pytest.param(
            CLASSIFIER,
            [("local_vision", None)],
            CLASSIFIER,
            id="preferred",
        ),
        pytest.param(
            None,
            [("other", None), ("local_vision", None)],
            "ai_task.local_vision",
            id="local_vision",
        ),
        pytest.param(
            None,
            [("local_vision", er.RegistryEntryDisabler.USER)],
            None,
            id="local_vision_disabled",
        ),
        pytest.param(None, [("other", None)], None, id="none"),
    ],
)
@pytest.mark.usefixtures("camera")
async def test_user_flow_ai_task_default(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    preferred: str | None,
    registered: list[tuple[str, er.RegistryEntryDisabler | None]],
    expected: str | None,
) -> None:
    """The preferred entity is suggested, else one of Local vision."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "classify_image_entity_id": preferred}
    )
    assert (await client.receive_json())["success"]
    for platform, disabled_by in registered:
        entity_registry.async_get_or_create(
            "ai_task",
            platform,
            platform,
            suggested_object_id=platform,
            disabled_by=disabled_by,
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert _suggested(result, CONF_AI_TASK_ENTITY_ID) == expected


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.usefixtures("camera")
async def test_user_flow_adjust_region(hass: HomeAssistant) -> None:
    """The preview menu leads back to the region."""
    flow_id = await _start(hass)
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    await hass.config_entries.flow.async_configure(flow_id, REGION)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "region"}
    )
    assert result["step_id"] == "region"

    new_region = {**REGION, CONF_LEFT: 12.5}
    await hass.config_entries.flow.async_configure(flow_id, new_region)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "finish"}
    )
    assert result["options"][CONF_REGION] == new_region


@pytest.mark.usefixtures("mock_setup_entry", "camera")
@pytest.mark.parametrize(
    ("region", "error"),
    [
        pytest.param({**REGION, CONF_LEFT: 80}, "invalid_horizontal_range", id="left"),
        pytest.param({**REGION, CONF_LEFT: 75}, "invalid_horizontal_range", id="width"),
        pytest.param({**REGION, CONF_TOP: 90}, "invalid_vertical_range", id="height"),
    ],
)
async def test_user_flow_invalid_region(
    hass: HomeAssistant, region: dict[str, float], error: str
) -> None:
    """An empty region is rejected, a valid one recovers."""
    flow_id = await _start(hass)
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    result = await hass.config_entries.flow.async_configure(flow_id, region)
    assert result["step_id"] == "region"
    assert result["errors"] == {"base": error}
    assert result["description_placeholders"]["preview"].startswith(PREVIEW_PREFIX)

    await hass.config_entries.flow.async_configure(flow_id, REGION)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("frame", "error"),
    [
        pytest.param(None, "cannot_connect", id="no_frame"),
        pytest.param(b"<html>502</html>", "invalid_frame", id="undecodable"),
    ],
)
async def test_user_flow_camera_errors(
    hass: HomeAssistant, camera: FakeCamera, frame: bytes | None, error: str
) -> None:
    """A camera without a usable frame shows an error until it answers."""
    camera.frame = frame
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["errors"] == {"base": error}
    assert _suggested(result, CONF_AI_TASK_ENTITY_ID) == CLASSIFIER

    camera.frame = render_frame(car=True)
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    await hass.config_entries.flow.async_configure(flow_id, REGION)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"next_step_id": "finish"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("camera")
async def test_options_menu_without_frames(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Removing is only offered once something was taught."""
    await setup_integration(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["teach", "ai_task"]


@pytest.mark.usefixtures("camera")
async def test_options_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Options abort instead of failing while the entry is not loaded."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def _unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_unload(entry.entry_id)


async def _unloading(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    # Unloading closes the frames before the entry state changes.
    entry.runtime_data.taught_frames.close()


@pytest.mark.parametrize(
    ("step", "user_input"),
    [
        pytest.param("teach", lambda stored: {"state": "on"}, id="teach"),
        pytest.param(
            "remove", lambda stored: {"frames": [stored[0]["id"]]}, id="remove"
        ),
    ],
)
@pytest.mark.parametrize("stop", [_unload, _unloading], ids=["unloaded", "unloading"])
async def test_options_change_after_unload(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    step: str,
    user_input: Callable[[list[dict[str, Any]]], dict[str, Any]],
    stop: Callable[[HomeAssistant, MockConfigEntry], Awaitable[None]],
) -> None:
    """A change in a dialog left open while the entry unloads is not stored."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    stored = stored_frames(hass_storage, mock_config_entry)
    flow_id = await _open(hass, mock_config_entry, step)
    await stop(hass, mock_config_entry)

    result = await hass.config_entries.options.async_configure(
        flow_id, user_input(stored)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"
    assert stored_frames(hass_storage, mock_config_entry) == stored


@pytest.mark.parametrize(
    ("device_class", "counts"),
    [("door", "Open: 0, Closed: 0"), ("occupancy", "Detected: 0, Clear: 0")],
)
async def test_options_teach(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    device_class: str,
    counts: str,
) -> None:
    """Teaching stores the shown frame with its state and keeps the options."""
    await setup_integration(hass, mock_config_entry)
    shown = camera.frame
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "teach"}
    )
    assert result["description_placeholders"]["preview"].startswith(PREVIEW_PREFIX)
    assert result["description_placeholders"]["counts"] == counts
    selector = result["data_schema"].schema["state"]
    assert selector.config["translation_key"] == f"state_{device_class}"
    assert selector.config["options"] == ["on", "off"]
    # The frame shown in the dialog is taught, not a later one.
    camera.frame = render_frame(car=False)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"state": "on"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "teach_successful"
    assert mock_config_entry.options[CONF_REGION] == REGION
    (stored,) = stored_frames(hass_storage, mock_config_entry)
    assert stored["label"] == "on"
    assert frame_files(config_dir, mock_config_entry) == {stored["id"]}
    path = config_dir / DOMAIN / mock_config_entry.entry_id / f"{stored['id']}.jpg"
    assert path.read_bytes() == prepare_frame(shown)


@pytest.mark.parametrize(
    ("frame", "reason"),
    [
        pytest.param(None, "cannot_connect", id="no_frame"),
        pytest.param(b"<html>502</html>", "invalid_frame", id="undecodable"),
    ],
)
async def test_options_teach_camera_errors(
    hass: HomeAssistant,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    frame: bytes | None,
    reason: str,
) -> None:
    """Teaching aborts when the camera has no usable frame."""
    await setup_integration(hass, mock_config_entry)
    camera.frame = frame
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "teach"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize("device_class", ["door"])
async def test_options_remove(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Selected frames are removed from the index and the disk."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    on, off = stored_frames(hass_storage, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["menu_options"] == ["teach", "remove", "ai_task"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove"}
    )
    labels = [
        option["label"]
        for option in result["data_schema"].schema["frames"].config["options"]
    ]
    assert [label.split(",")[0] for label in labels] == ["Open", "Closed"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"frames": []}
    )
    assert result["errors"] == {"base": "nothing_selected"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"frames": [off["id"]]}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "remove_successful"
    assert stored_frames(hass_storage, mock_config_entry) == [on]
    assert frame_files(config_dir, mock_config_entry) == {on["id"]}


async def test_options_teach_survives_closed_dialog(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    camera: FakeCamera,
) -> None:
    """Closing the dialog while the frame is stored still stores it completely."""
    await setup_integration(hass, mock_config_entry)
    flow_id = await _open(hass, mock_config_entry, "teach")
    step = hass.async_create_task(
        hass.config_entries.options.async_configure(flow_id, {"state": "on"})
    )
    # The step now waits for the executor, as when the request is dropped.
    await asyncio.sleep(0)
    step.cancel()
    await hass.async_block_till_done()

    (stored,) = stored_frames(hass_storage, mock_config_entry)
    assert frame_files(config_dir, mock_config_entry) == {stored["id"]}


async def test_options_change_ai_task_entity(
    hass: HomeAssistant,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Another AI Task entity can be chosen, the entry reloads with it."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_AI_TASK_ENTITY_ID: "ai_task.gone"},
    )
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ai_task"}
    )
    assert _suggested(result, CONF_AI_TASK_ENTITY_ID) == "ai_task.gone"
    calls = len(classifier.tasks)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AI_TASK_ENTITY_ID: CLASSIFIER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_AI_TASK_ENTITY_ID] == CLASSIFIER
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # The reload classifies with the chosen entity right away.
    assert len(classifier.tasks) == calls + 1
