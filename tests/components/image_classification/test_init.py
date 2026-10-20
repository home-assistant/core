"""Tests for setting up Image classification."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from PIL import Image
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.image_classification.const import (
    CONF_AI_TASK_ENTITY_ID,
    DOMAIN,
)
from homeassistant.components.image_classification.frame_source import FRAME_SIDE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    CAMERA,
    CLASSIFIER,
    CONFIDENT_OFF,
    ENTITY_ID,
    FakeCamera,
    FakeClassifier,
    frame_files,
    render_frame,
    setup_integration,
    stored_frames,
    teach,
    teach_both,
)


@pytest.mark.usefixtures("camera")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_untaught_entry_ignores_camera(
    hass: HomeAssistant,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Without taught frames neither the camera nor the AI Task entity is asked."""
    camera.frame = None
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
    assert classifier.tasks == []


async def test_camera_offline_keeps_entry_loaded(
    hass: HomeAssistant, camera: FakeCamera, mock_config_entry: MockConfigEntry
) -> None:
    """While the camera is offline the sensor is unavailable, the options work."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    camera.frame = None

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["menu_options"] == ["teach", "remove", "ai_task"]


async def test_camera_checked_once_started(
    hass: HomeAssistant,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
) -> None:
    """During startup the sources may not be ready, they are asked once started."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    classifier.probabilities = CONFIDENT_OFF
    hass.set_state(CoreState.starting)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    "frame",
    [
        pytest.param(render_frame(car=True, size=(3840, 2160)), id="4k"),
        pytest.param(render_frame(car=True, image_format="PNG"), id="png"),
    ],
)
async def test_stored_frames_are_normalized(
    hass: HomeAssistant,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    frame: bytes,
) -> None:
    """Frames are stored as JPEG of a bounded size, as the media source says."""
    await setup_integration(hass, mock_config_entry)
    camera.frame = frame
    await teach(hass, mock_config_entry, "on")

    (frame_id,) = frame_files(config_dir, mock_config_entry)
    path = config_dir / DOMAIN / mock_config_entry.entry_id / f"{frame_id}.jpg"
    with Image.open(path) as stored:
        assert stored.format == "JPEG"
        assert max(stored.size) <= FRAME_SIDE


async def test_frames_survive_reload(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Taught frames are used again after a reload."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    stored = stored_frames(hass_storage, mock_config_entry)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert stored_frames(hass_storage, mock_config_entry) == stored
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["menu_options"] == ["teach", "remove", "ai_task"]


async def test_unusable_frames_are_dropped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Damaged and missing frames are dropped instead of breaking the entry."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    await teach(hass, mock_config_entry, "on")
    damaged, missing, kept = (
        item["id"] for item in stored_frames(hass_storage, mock_config_entry)
    )
    folder = config_dir / DOMAIN / mock_config_entry.entry_id
    path = folder / f"{damaged}.jpg"
    path.write_bytes(path.read_bytes()[:200])
    (folder / f"{missing}.jpg").unlink()
    (folder / "stray.jpg").write_bytes(b"left over")

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert [item["id"] for item in stored_frames(hass_storage, mock_config_entry)] == [
        kept
    ]
    # Files without an index entry stay, they may be the only copy.
    assert frame_files(config_dir, mock_config_entry) == {kept, "stray"}
    assert f"Dropping taught frame {damaged}: undecodable" in caplog.text
    assert f"Dropping taught frame {missing}: file missing" in caplog.text


async def test_damaged_index_keeps_frames(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Without a readable index the frames on disk are kept for a restore."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    files = frame_files(config_dir, mock_config_entry)
    hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"]["data"] = [
        "not",
        "a",
        "dict",
    ]

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert frame_files(config_dir, mock_config_entry) == files


@pytest.mark.parametrize(
    "item",
    [
        pytest.param({"id": "../../secrets", "label": "on"}, id="path"),
        pytest.param({"id": "0" * 32, "created": "2026-10-19T18:00:00"}, id="label"),
        pytest.param(
            {"id": "0" * 32, "label": "maybe", "created": "2026-10-19T18:00:00"},
            id="unknown_label",
        ),
        pytest.param({"id": "0" * 32, "label": "on", "created": "noon"}, id="created"),
    ],
)
async def test_invalid_index_items_are_dropped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    item: dict[str, Any],
) -> None:
    """Index items that can't be used are dropped, the others stay."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    stored = list(stored_frames(hass_storage, mock_config_entry))
    stored_frames(hass_storage, mock_config_entry).append(item)

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert stored_frames(hass_storage, mock_config_entry) == stored
    assert "Dropping invalid taught frame entry" in caplog.text
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["menu_options"] == ["teach", "remove", "ai_task"]


async def test_unknown_stored_fields_survive(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Fields written by a newer version are kept on the next save."""
    await setup_integration(hass, mock_config_entry)
    await teach(hass, mock_config_entry, "on")
    key = f"{DOMAIN}.{mock_config_entry.entry_id}"
    hass_storage[key]["data"]["frames"][0]["source"] = "history"
    hass_storage[key]["data"]["burst"] = {"frames": 3}
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    camera.frame = render_frame(car=False)
    await teach(hass, mock_config_entry, "off")

    assert hass_storage[key]["data"]["frames"][0]["source"] == "history"
    assert hass_storage[key]["data"]["burst"] == {"frames": 3}


async def test_cap_drops_oldest_frames(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Teaching beyond the cap of a state drops its oldest frame and file."""
    with patch(
        "homeassistant.components.image_classification.taught_frames.MAX_FRAMES_PER_STATE",
        2,
    ):
        await setup_integration(hass, mock_config_entry)
        await teach_both(hass, mock_config_entry, camera)
        await teach(hass, mock_config_entry, "on")
        _, off, second = stored_frames(hass_storage, mock_config_entry)
        await teach(hass, mock_config_entry, "on")

    stored = stored_frames(hass_storage, mock_config_entry)
    assert stored[:2] == [off, second]
    assert [item["label"] for item in stored] == ["off", "on", "on"]
    assert frame_files(config_dir, mock_config_entry) == {item["id"] for item in stored}


async def test_cap_applies_on_load(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Frames stored beyond a lower cap are dropped when the entry loads."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    await teach(hass, mock_config_entry, "on")
    _, off, second = stored_frames(hass_storage, mock_config_entry)

    with patch(
        "homeassistant.components.image_classification.taught_frames.MAX_FRAMES_PER_STATE",
        1,
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert stored_frames(hass_storage, mock_config_entry) == [off, second]
    assert frame_files(config_dir, mock_config_entry) == {off["id"], second["id"]}


@pytest.mark.usefixtures("camera")
async def test_follows_renamed_ai_task_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A renamed AI Task entity is followed and the entry reloads."""
    await setup_integration(hass, mock_config_entry)

    entity_registry.async_update_entity(CLASSIFIER, name="Garage classifier")
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_AI_TASK_ENTITY_ID] == CLASSIFIER

    entity_registry.async_update_entity(CLASSIFIER, new_entity_id="ai_task.garage")
    await hass.async_block_till_done()

    assert mock_config_entry.options[CONF_AI_TASK_ENTITY_ID] == "ai_task.garage"
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_removed_ai_task_entity_stays_configured(
    hass: HomeAssistant,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Without its AI Task entity the sensor is unavailable, the option stays."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)

    entity_registry.async_remove(CLASSIFIER)
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.options[CONF_AI_TASK_ENTITY_ID] == CLASSIFIER
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("camera")
async def test_remove_deletes_everything(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """Removing the entry deletes its frames and index."""
    await setup_integration(hass, mock_config_entry)
    await teach(hass, mock_config_entry, "on")
    assert (config_dir / DOMAIN).is_dir()

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not (config_dir / DOMAIN / mock_config_entry.entry_id).exists()
    assert f"{DOMAIN}.{mock_config_entry.entry_id}" not in hass_storage


@pytest.mark.usefixtures("camera")
async def test_remove_keeps_other_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    config_dir: Path,
) -> None:
    """The shared folder stays while another entry has frames in it."""
    other = MockConfigEntry(
        domain=DOMAIN, title="Bike", options=dict(mock_config_entry.options)
    )
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, other)
    await teach(hass, mock_config_entry, "on")
    await teach(hass, other, "on")

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(frame_files(config_dir, other)) == 1


@pytest.mark.usefixtures("camera")
async def test_follows_renamed_camera(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A renamed camera entity is followed and the entry reloads."""
    await setup_integration(hass, mock_config_entry)

    entity_registry.async_update_entity(CAMERA, new_entity_id="camera.garage_left")
    await hass.async_block_till_done()

    assert mock_config_entry.options[CONF_ENTITY_ID] == "camera.garage_left"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
