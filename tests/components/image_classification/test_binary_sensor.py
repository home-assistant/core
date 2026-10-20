"""Tests for the Image classification binary sensor."""

from datetime import timedelta
from pathlib import Path
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task
from homeassistant.components.image_classification.const import (
    CONF_AI_TASK_ENTITY_ID,
    DOMAIN,
    UPDATE_INTERVAL,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    CAMERA,
    CONFIDENT_OFF,
    CONFIDENT_ON,
    ENTITY_ID,
    FakeCamera,
    FakeClassifier,
    render_frame,
    setup_integration,
    stored_frames,
    teach,
    teach_both,
)


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    # The coordinator spreads its refreshes over the second.
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.usefixtures("camera")
async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The sensor joins the camera device and is named after it."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    sensor = entity_registry.async_get(ENTITY_ID)
    assert sensor.device_id == entity_registry.async_get(CAMERA).device_id
    assert hass.states.get(ENTITY_ID).name == "Garage camera Garage"


@pytest.mark.parametrize("device_class", ["door", "garage_door", "window"])
@pytest.mark.usefixtures("camera")
async def test_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_class: str,
) -> None:
    """The configured device class is used."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_DEVICE_CLASS] == device_class


async def test_unknown_until_taught(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
) -> None:
    """With one state taught there is nothing to compare, nothing is asked."""
    await setup_integration(hass, mock_config_entry)
    await teach(hass, mock_config_entry, "on")
    camera.frame = None
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
    assert classifier.tasks == []


@pytest.mark.parametrize(
    ("probabilities", "expected"),
    [
        pytest.param(CONFIDENT_ON, STATE_ON, id="on"),
        pytest.param(CONFIDENT_OFF, STATE_OFF, id="off"),
        pytest.param({"on": 0.79, "off": 0.21}, STATE_UNKNOWN, id="unsure_on"),
        pytest.param({"on": 0.3, "off": 0.7}, STATE_UNKNOWN, id="unsure_off"),
    ],
)
async def test_state_follows_probabilities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
    probabilities: dict[str, float],
    expected: str,
) -> None:
    """A state needs a probability of 0.8, the sensor is unknown while unsure."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    classifier.probabilities = probabilities
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == expected


async def test_classification_task(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    config_dir: Path,
) -> None:
    """The live camera frame is classified by the taught frames in the region."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    camera.frame = render_frame(car=True)
    await _poll(hass, freezer)

    task = classifier.tasks[-1]
    assert classifier.images[-1] == camera.frame
    assert task.name == "Garage"
    assert task.image.media_content_id == f"media-source://camera/{CAMERA}"
    assert task.region == ai_task.Region(left=0.25, top=0.2, right=0.75, bottom=0.9)
    folder = config_dir / DOMAIN / mock_config_entry.entry_id
    prefix = f"media-source://{DOMAIN}/{mock_config_entry.entry_id}"
    assert {
        label: [
            (example.media_content_id, example.path, example.mime_type)
            for example in image_label.examples
        ]
        for label, image_label in task.labels.items()
    } == {
        item["label"]: [
            (
                f"{prefix}/{item['id']}.jpg",
                folder / f"{item['id']}.jpg",
                "image/jpeg",
            )
        ]
        for item in stored_frames(hass_storage, mock_config_entry)
    }


async def test_uses_the_chosen_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the configured AI Task entity classifies, without falling back."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_AI_TASK_ENTITY_ID: "ai_task.gone"},
    )
    calls = len(classifier.tasks)
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert len(classifier.tasks) == calls
    assert "Could not classify the frame: AI Task entity ai_task.gone not found" in (
        caplog.text
    )


@pytest.mark.parametrize(
    ("frame", "error", "message"),
    [
        pytest.param(None, None, "Unable to get image", id="no_frame"),
        pytest.param(
            render_frame(car=True),
            HomeAssistantError("model broke"),
            "model broke",
            id="classification_error",
        ),
    ],
)
async def test_unavailable_on_errors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    classifier: FakeClassifier,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    frame: bytes | None,
    error: Exception | None,
    message: str,
) -> None:
    """A failed classification makes the sensor unavailable until it recovers."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    camera.frame = frame
    classifier.error = error
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert f"Error fetching Garage data: Could not classify the frame: {message}" in (
        caplog.text
    )

    camera.frame = render_frame(car=True)
    classifier.error = None
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_ON
