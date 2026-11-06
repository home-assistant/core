"""Test DoorBird cameras."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.camera import (
    CameraState,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.doorbird.const import (
    CONF_EVENTS,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_MOTION_EVENT,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import VALID_CONFIG, mock_not_found_exception
from .conftest import DoorbirdMockerType

LIVE_CAMERA_ENTITY_ID = "camera.mydoorbird_live"
LAST_RING_CAMERA_ENTITY_ID = "camera.mydoorbird_last_ring"
LAST_MOTION_CAMERA_ENTITY_ID = "camera.mydoorbird_last_motion"
LAST_RING_ISSUE_ID = "deprecated_camera_1234ABCD_last_ring"


def create_stale_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Create a repair issue left over from an earlier setup."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_camera_last_ring",
        translation_placeholders={
            "entity_id": LAST_RING_CAMERA_ENTITY_ID,
            "entity_name": "Last ring",
            "docs_url": "",
        },
    )


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
    create_stale_issue(hass, f"deprecated_camera_1234ABCD_{camera_id}")

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

    doorbird_entry = await doorbird_mocker()

    assert hass.states.get(entity_id).state == CameraState.IDLE
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_camera_1234ABCD_{camera_id}"
    )
    assert issue is not None
    assert issue.translation_key == f"deprecated_camera_{camera_id}"
    assert issue.translation_placeholders["entity_id"] == entity_id
    assert issue.config_entry_id == doorbird_entry.entry.entry_id


async def test_deprecated_camera_issue_names_renamed_entity(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue names the entity id the user gave the camera."""
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        "1234ABCD_last_ring",
        suggested_object_id="front_door_ring_snapshot",
    )

    await doorbird_mocker()

    issue = issue_registry.async_get_issue(DOMAIN, LAST_RING_ISSUE_ID)
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
    create_stale_issue(hass, f"deprecated_camera_1234ABCD_{camera_id}")

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


async def test_deprecated_camera_kept_when_disabled_by_device(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a camera disabled along with its device is neither removed nor flagged."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1CCAE3AAAAAA",
        data=VALID_CONFIG,
        options={CONF_EVENTS: [DEFAULT_DOORBELL_EVENT, DEFAULT_MOTION_EVENT]},
    )
    entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "1234ABCD")},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        "1234ABCD_last_ring",
        config_entry=entry,
        device_id=device_entry.id,
        suggested_object_id="mydoorbird_last_ring",
    )
    create_stale_issue(hass, LAST_RING_ISSUE_ID)

    await doorbird_mocker(entry=entry)

    assert entity_registry.async_get(LAST_RING_CAMERA_ENTITY_ID) is not None
    assert (DOMAIN, LAST_RING_ISSUE_ID) not in issue_registry.issues


@pytest.mark.parametrize(
    ("automation_id", "expected_item"),
    [
        pytest.param(
            {"id": "test_automation"},
            "[test_automation](/config/automation/edit/test_automation)",
            id="registered",
        ),
        pytest.param({}, "`automation.test_automation`", id="yaml_without_id"),
    ],
)
async def test_deprecated_camera_issue_lists_automations(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    automation_id: dict[str, str],
    expected_item: str,
) -> None:
    """Test the issue lists the automations still using the camera."""
    entity_registry.async_get_or_create(
        Platform.CAMERA,
        DOMAIN,
        "1234ABCD_last_ring",
        suggested_object_id="mydoorbird_last_ring",
    )
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                **automation_id,
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

    issue = issue_registry.async_get_issue(DOMAIN, LAST_RING_ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "deprecated_camera_last_ring_scripts"
    assert issue.translation_placeholders["items"] == f"- {expected_item}"
