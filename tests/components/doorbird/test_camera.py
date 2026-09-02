"""Test DoorBird cameras."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.camera import (
    CameraState,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.doorbird.const import CONF_EVENTS, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import mock_not_found_exception
from .conftest import DoorbirdMockerType

LIVE_CAMERA_ENTITY_ID = "camera.mydoorbird_live"
LAST_RING_CAMERA_ENTITY_ID = "camera.mydoorbird_last_ring"
LAST_MOTION_CAMERA_ENTITY_ID = "camera.mydoorbird_last_motion"


async def test_doorbird_live_camera(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the live camera, which has no image entity replacement."""
    doorbird_entry = await doorbird_mocker()
    assert hass.states.get(LIVE_CAMERA_ENTITY_ID).state == CameraState.IDLE
    assert await async_get_stream_source(hass, LIVE_CAMERA_ENTITY_ID) is not None
    api = doorbird_entry.api
    api.get_image.side_effect = mock_not_found_exception()
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, LIVE_CAMERA_ENTITY_ID)
    api.get_image.side_effect = TimeoutError()
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, LIVE_CAMERA_ENTITY_ID)
    api.get_image.side_effect = None
    assert (await async_get_image(hass, LIVE_CAMERA_ENTITY_ID)).content == b"image"
    api.get_image.return_value = b"notyet"
    # Ensure rate limit works
    assert (await async_get_image(hass, LIVE_CAMERA_ENTITY_ID)).content == b"image"

    freezer.tick(60)
    assert (await async_get_image(hass, LIVE_CAMERA_ENTITY_ID)).content == b"notyet"


@pytest.mark.parametrize(
    ("camera_id", "entity_id"),
    [
        pytest.param("last_ring", LAST_RING_CAMERA_ENTITY_ID, id="last_ring"),
        pytest.param("last_motion", LAST_MOTION_CAMERA_ENTITY_ID, id="last_motion"),
    ],
)
async def test_deprecated_camera_not_created_for_new_installs(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    camera_id: str,
    entity_id: str,
) -> None:
    """Test the deprecated still cameras are not created on a fresh install."""
    await doorbird_mocker()

    assert hass.states.get(entity_id) is None
    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"1234ABCD_{camera_id}"
        )
        is None
    )
    assert (
        DOMAIN,
        f"deprecated_camera_1234ABCD_{camera_id}",
    ) not in issue_registry.issues


@pytest.mark.parametrize(
    ("camera_id", "entity_id"),
    [
        pytest.param("last_ring", LAST_RING_CAMERA_ENTITY_ID, id="last_ring"),
        pytest.param("last_motion", LAST_MOTION_CAMERA_ENTITY_ID, id="last_motion"),
    ],
)
async def test_deprecated_camera_kept_and_flagged(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    camera_id: str,
    entity_id: str,
) -> None:
    """Test an existing still camera is kept and raises a repair issue."""
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"1234ABCD_{camera_id}",
        suggested_object_id=f"mydoorbird_{camera_id}",
    )

    await doorbird_mocker()

    assert hass.states.get(entity_id).state == CameraState.IDLE
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_camera_1234ABCD_{camera_id}"
    )
    assert issue is not None
    assert issue.translation_key == f"deprecated_camera_{camera_id}"
    assert issue.translation_placeholders["entity_id"] == entity_id


async def test_deprecated_camera_issue_survives_rename(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A renamed legacy camera still gets an issue naming its own entity id."""
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        "1234ABCD_last_ring",
        suggested_object_id="front_door_ring_snapshot",
    )

    await doorbird_mocker()

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_camera_1234ABCD_last_ring"
    )
    assert issue is not None
    assert issue.translation_placeholders["entity_id"] == (
        "camera.front_door_ring_snapshot"
    )


@pytest.mark.parametrize(
    "camera_id",
    [
        pytest.param("last_ring", id="last_ring"),
        pytest.param("last_motion", id="last_motion"),
    ],
)
async def test_deprecated_camera_removed_when_disabled(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    camera_id: str,
) -> None:
    """Test a disabled still camera is removed and the repair issue cleared."""
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        f"1234ABCD_{camera_id}",
        suggested_object_id=f"mydoorbird_{camera_id}",
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await doorbird_mocker()

    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, f"1234ABCD_{camera_id}"
        )
        is None
    )
    assert (
        DOMAIN,
        f"deprecated_camera_1234ABCD_{camera_id}",
    ) not in issue_registry.issues


async def test_deprecated_camera_kept_when_used_by_automation(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a disabled still camera used by an automation is kept and flagged."""
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        "1234ABCD_last_ring",
        suggested_object_id="mydoorbird_last_ring",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                "alias": "test_automation",
                "triggers": {
                    "trigger": "state",
                    "entity_id": LAST_RING_CAMERA_ENTITY_ID,
                },
                "actions": {"action": "notify.notify", "data": {}},
            }
        },
    )

    await doorbird_mocker()

    assert (
        entity_registry.async_get_entity_id(
            Platform.CAMERA, DOMAIN, "1234ABCD_last_ring"
        )
        is not None
    )
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_camera_1234ABCD_last_ring"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_camera_last_ring_scripts"


@pytest.mark.parametrize(
    "configured_events",
    [
        pytest.param([], id="no_events"),
        pytest.param([""], id="cleared_in_the_options"),
    ],
)
async def test_camera_kept_without_configured_events(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    configured_events: list[str],
) -> None:
    """Test the deprecated cameras stay when no event can refresh the images."""
    await doorbird_mocker(options={CONF_EVENTS: configured_events})

    assert hass.states.get("camera.mydoorbird_last_ring") is not None
    assert hass.states.get("camera.mydoorbird_last_motion") is not None
