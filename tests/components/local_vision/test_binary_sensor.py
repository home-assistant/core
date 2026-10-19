"""Tests for the Local vision binary sensor."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.local_vision.const import UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    CAMERA,
    ENTITY_ID,
    FakeCamera,
    blank_frame,
    render_frame,
    setup_integration,
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
    mock_config_entry: MockConfigEntry,
) -> None:
    """With one state taught there is nothing to compare, the camera is not asked."""
    await setup_integration(hass, mock_config_entry)
    await teach(hass, mock_config_entry, "on")
    camera.frame = None
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("frame", "expected"),
    [
        pytest.param(
            render_frame(car=True, shift=2, brightness=0.8), STATE_ON, id="car"
        ),
        pytest.param(render_frame(car=False, shift=2), STATE_OFF, id="empty"),
        pytest.param(
            render_frame(car=False, corner=True), STATE_OFF, id="change_outside"
        ),
    ],
)
async def test_classifies_new_frames(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    frame: bytes,
    expected: str,
) -> None:
    """New frames get the taught state; changes outside the region do not count."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    camera.frame = frame
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == expected


async def test_teaches_the_shown_frame(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The frame shown in the dialog is stored, not a later one."""
    await setup_integration(hass, mock_config_entry)
    camera.frame = render_frame(car=True)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "teach"}
    )
    camera.frame = render_frame(car=False)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"state": "on"}
    )
    await teach(hass, mock_config_entry, "off")

    camera.frame = render_frame(car=True)
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("camera")
async def test_unsure_is_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A frame that matches both states equally is unknown."""
    await setup_integration(hass, mock_config_entry)
    await teach(hass, mock_config_entry, "on")
    await teach(hass, mock_config_entry, "off")
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        pytest.param(
            None,
            f"Could not get a frame from {CAMERA}: Unable to get image",
            id="no_frame",
        ),
        pytest.param(
            b"not an image",
            "The camera returned an image that could not be decoded: "
            "cannot decode image",
            id="undecodable",
        ),
    ],
)
async def test_unavailable_without_frame(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    frame: bytes | None,
    message: str,
) -> None:
    """No usable frame makes the sensor unavailable until the camera recovers."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    camera.frame = frame
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert f"Error fetching Garage data: {message}" in caplog.text

    camera.frame = render_frame(car=True)
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    "frame",
    [
        pytest.param(blank_frame(), id="blank_frame"),
        pytest.param(render_frame(car=False, plain=True, corner=True), id="plain"),
    ],
)
async def test_nothing_to_compare_is_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    camera: FakeCamera,
    mock_config_entry: MockConfigEntry,
    frame: bytes,
) -> None:
    """A dark frame or a plain region is unknown, not a camera error."""
    await setup_integration(hass, mock_config_entry)
    await teach_both(hass, mock_config_entry, camera)
    camera.frame = frame
    await _poll(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
