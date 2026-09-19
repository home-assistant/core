"""Test the UniFi Protect switch platform."""

from collections.abc import Callable, Coroutine
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from uiprotect.data import (
    Camera,
    Light,
    Permission,
    PublicHdrMode,
    RecordingMode,
    Sensor,
    SmartDetectAudioType,
    SmartDetectObjectType,
    VideoMode,
    WSAction,
)
from uiprotect.data.public_devices import SensorFeatureCapability
from uiprotect.exceptions import ClientError, NotAuthorized

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION, DOMAIN
from homeassistant.components.unifiprotect.switch import (
    ATTR_PREV_MIC,
    ATTR_PREV_RECORD,
    CAMERA_SWITCHES,
    LIGHT_SWITCHES,
    PRIVACY_MODE_SWITCH,
    SENSE_SWITCHES,
    ProtectSwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import async_get_platforms

from . import patch_ufp_method
from .conftest import UNIFI_MAC
from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    ids_from_device_description,
    init_entry,
    make_public_camera,
    make_public_light,
    make_public_sensor,
    public_device_ws_message,
    remove_entities,
    setup_public_camera,
    setup_public_light,
    setup_public_sensor,
)

CAMERA_SWITCHES_BASIC = [
    d
    for d in CAMERA_SWITCHES
    if (
        not d.translation_key.startswith("detections_")
        and d.key not in {"ssh", "color_night_vision", "track_person", "hdr_mode"}
    )
    or d.key
    in {
        "detections_motion",
        "detections_person",
        "detections_vehicle",
        "detections_animal",
    }
]
CAMERA_SWITCHES_NO_EXTRA = [
    d
    for d in CAMERA_SWITCHES_BASIC
    if d.key not in ("high_fps", "privacy_mode", "hdr_mode")
]
CAMERA_SWITCHES_PRIVATE = [d for d in CAMERA_SWITCHES_NO_EXTRA if not d.is_public_value]
CAMERA_SWITCHES_PUBLIC = [d for d in CAMERA_SWITCHES_NO_EXTRA if d.is_public_value]


async def test_switch_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 2, 2)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)


async def test_switch_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 2, 2)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)


async def test_switch_nvr(hass: HomeAssistant, ufp: MockUFPFixture) -> None:
    """Test switch entity setup for light devices."""

    await init_entry(hass, ufp, [])

    assert_entity_counts(hass, Platform.SWITCH, 2, 2)

    nvr = ufp.api.bootstrap.nvr
    entity_id = "switch.unifiprotect_insights_enabled"

    with patch_ufp_method(nvr, "set_insights", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_once_with(True)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_with(False)


async def test_switch_setup_no_perm(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    doorbell: Camera,
) -> None:
    """Test switch entity setup for light devices."""

    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict({"rawPermission": "light:read:*"})
    ]

    await init_entry(hass, ufp, [light, doorbell])

    assert_entity_counts(hass, Platform.SWITCH, 0, 0)


async def test_switch_setup_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test switch entity setup for light devices."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)

    description = LIGHT_SWITCHES[1]

    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, light, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    description = LIGHT_SWITCHES[0]

    unique_id = f"{light.mac}_{description.key}"
    entity_id = f"switch.test_light_{description.translation_key}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_setup_camera_all(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test switch entity setup for camera devices (all enabled feature flags)."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    for description in CAMERA_SWITCHES_BASIC:
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, doorbell, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    description = CAMERA_SWITCHES[0]

    unique_id = f"{doorbell.mac}_{description.key}"
    entity_id = f"switch.test_camera_{description.translation_key}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_setup_camera_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test switch entity setup for camera devices (no enabled feature flags)."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.SWITCH, 8, 7)

    for description in CAMERA_SWITCHES_BASIC:
        if description.ufp_required_field is not None:
            continue

        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    description = CAMERA_SWITCHES[0]

    unique_id = f"{camera.mac}_{description.key}"
    entity_id = f"switch.test_camera_{description.translation_key}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is True
    assert entity.unique_id == unique_id

    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_switch_light_status(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Tests status light switch for lights."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.SWITCH, 4, 3)

    description = LIGHT_SWITCHES[1]

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, light, description
    )

    public = make_public_light(light)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(
        public, "set_status_light", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_once_with(True)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_with(False)


async def test_switch_light_status_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Status light switch reads from the public object and refreshes on a WS update."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, light, LIGHT_SWITCHES[1]
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    # The private fixture has the indicator disabled; the public ON proves the source.
    public = make_public_light(light, is_indicator_enabled=True)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_light_status_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """The migrated status light switch is unavailable without a public object."""

    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, light, LIGHT_SWITCHES[1]
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_switch_camera_ssh(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Tests SSH switch for cameras."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = CAMERA_SWITCHES[0]

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    with patch_ufp_method(doorbell, "set_ssh", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_once_with(True)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_with(False)


@pytest.mark.parametrize("description", CAMERA_SWITCHES_PRIVATE)
async def test_switch_camera_simple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    description: ProtectSwitchEntityDescription,
) -> None:
    """Tests the private-API camera switches."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    assert description.ufp_set_method is not None

    with patch_ufp_method(
        doorbell, description.ufp_set_method, new_callable=AsyncMock
    ) as mock_method:
        _, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, doorbell, description
        )

        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_once_with(True)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_with(False)


@pytest.mark.parametrize("description", CAMERA_SWITCHES_PUBLIC)
async def test_switch_camera_simple_public(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    description: ProtectSwitchEntityDescription,
) -> None:
    """The migrated camera switches write through the public object."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    assert description.ufp_set_method is not None

    public = make_public_camera(doorbell)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(
        public, description.ufp_set_method, new_callable=AsyncMock
    ) as mock_method:
        _, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, doorbell, description
        )

        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_once_with(True)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_with(False)


async def test_switch_camera_highfps(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Tests High FPS switch for cameras."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = CAMERA_SWITCHES[3]

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )

    public = make_public_camera(doorbell)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(public, "set_video_mode", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_once_with(VideoMode.HIGH_FPS)

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_called_with(VideoMode.DEFAULT)


CAMERA_SWITCHES_DETECTIONS_EXTRA = [
    d
    for d in CAMERA_SWITCHES
    if d.translation_key.startswith("detections_")
    and d.key
    not in {
        "detections_motion",
        "detections_person",
        "detections_vehicle",
        "detections_animal",
    }
]


async def test_switch_camera_hdr(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Tests HDR mode switch uses the public API helper."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = next(d for d in CAMERA_SWITCHES if d.key == "hdr_mode")

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    await enable_entity(hass, ufp.entry.entry_id, entity_id)

    with patch_ufp_method(
        doorbell, "set_hdr_mode_public", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_has_calls(
            [call(PublicHdrMode.AUTO), call(PublicHdrMode.OFF)]
        )
        assert mock_method.call_count == 2


@pytest.mark.parametrize("description", CAMERA_SWITCHES_DETECTIONS_EXTRA)
async def test_switch_camera_detections_public_api(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    description: ProtectSwitchEntityDescription,
) -> None:
    """Tests detection switches call the public API setters."""

    doorbell.feature_flags.smart_detect_types = [
        SmartDetectObjectType.PERSON,
        SmartDetectObjectType.VEHICLE,
        SmartDetectObjectType.ANIMAL,
        SmartDetectObjectType.PACKAGE,
        SmartDetectObjectType.LICENSE_PLATE,
    ]
    doorbell.feature_flags.smart_detect_audio_types = [
        SmartDetectAudioType.SMOKE,
        SmartDetectAudioType.CMONX,
        SmartDetectAudioType.SIREN,
        SmartDetectAudioType.BABY_CRY,
        SmartDetectAudioType.SPEAK,
        SmartDetectAudioType.BARK,
        SmartDetectAudioType.BURGLAR,
        SmartDetectAudioType.CAR_HORN,
        SmartDetectAudioType.GLASS_BREAK,
    ]

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    assert description.ufp_set_method is not None
    assert description.ufp_capability is not None

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )

    public = make_public_camera(doorbell)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(
        public, description.ufp_set_method, new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_method.assert_has_calls([call(True), call(False)])
        assert mock_method.call_count == 2


async def test_switch_camera_status_light_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Status light reads from the public object and refreshes on a public WS update."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    description = next(d for d in CAMERA_SWITCHES if d.key == "status_light")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    public = make_public_camera(doorbell, status_light=True)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize(
    ("switch_key", "camera_kwarg"),
    [
        ("osd_name", "osd_name"),
        ("osd_date", "osd_date"),
        ("osd_logo", "osd_logo"),
        ("osd_bitrate", "osd_debug"),
    ],
)
async def test_switch_camera_osd_public_value(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    switch_key: str,
    camera_kwarg: str,
) -> None:
    """Each OSD switch reads its own public osd_settings flag independently."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    description = next(d for d in CAMERA_SWITCHES if d.key == switch_key)
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    public = make_public_camera(doorbell, **{camera_kwarg: True})
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


# Only the switch under test is enabled; ``make_public_camera`` defaults both
# lists to every type, so each case pins both to keep the others off.
CAMERA_SWITCHES_DETECTION_READ = [
    ("smart_person", [SmartDetectObjectType.PERSON], []),
    ("smart_vehicle", [SmartDetectObjectType.VEHICLE], []),
    ("smart_animal", [SmartDetectObjectType.ANIMAL], []),
    ("smart_package", [SmartDetectObjectType.PACKAGE], []),
    ("smart_licenseplate", [SmartDetectObjectType.LICENSE_PLATE], []),
    ("smart_smoke", [], [SmartDetectAudioType.SMOKE]),
    ("smart_cmonx", [], [SmartDetectAudioType.CMONX]),
    ("smart_siren", [], [SmartDetectAudioType.SIREN]),
    ("smart_baby_cry", [], [SmartDetectAudioType.BABY_CRY]),
    ("smart_speak", [], [SmartDetectAudioType.SPEAK]),
    ("smart_bark", [], [SmartDetectAudioType.BARK]),
    ("smart_car_alarm", [], [SmartDetectAudioType.BURGLAR]),
    ("smart_car_horn", [], [SmartDetectAudioType.CAR_HORN]),
    ("smart_glass_break", [], [SmartDetectAudioType.GLASS_BREAK]),
]


@pytest.mark.parametrize(
    ("key", "object_types", "audio_types"), CAMERA_SWITCHES_DETECTION_READ
)
async def test_switch_camera_detection_public_value(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    key: str,
    object_types: list[SmartDetectObjectType],
    audio_types: list[SmartDetectAudioType],
) -> None:
    """Each detection toggle reads its on/off state from its own public flag."""

    doorbell.feature_flags.smart_detect_types = [
        SmartDetectObjectType.PERSON,
        SmartDetectObjectType.VEHICLE,
        SmartDetectObjectType.ANIMAL,
        SmartDetectObjectType.PACKAGE,
        SmartDetectObjectType.LICENSE_PLATE,
    ]
    doorbell.feature_flags.smart_detect_audio_types = [
        SmartDetectAudioType.SMOKE,
        SmartDetectAudioType.CMONX,
        SmartDetectAudioType.SIREN,
        SmartDetectAudioType.BABY_CRY,
        SmartDetectAudioType.SPEAK,
        SmartDetectAudioType.BARK,
        SmartDetectAudioType.BURGLAR,
        SmartDetectAudioType.CAR_HORN,
        SmartDetectAudioType.GLASS_BREAK,
    ]

    setup_public_camera(ufp)

    async def _prime_without_camera() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_without_camera)

    await init_entry(hass, ufp, [doorbell])

    description = next(d for d in CAMERA_SWITCHES if d.key == key)
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )

    all_off = make_public_camera(doorbell, object_types=[], audio_types=[])
    ufp.devices_ws_subscription(public_device_ws_message(all_off))
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    public = make_public_camera(
        doorbell, object_types=object_types, audio_types=audio_types
    )
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_camera_highfps_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """The high FPS switch reads video_mode from the public object."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    description = next(d for d in CAMERA_SWITCHES if d.key == "high_fps")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    public = make_public_camera(doorbell, video_mode=VideoMode.HIGH_FPS)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_camera_detection_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """A migrated detection toggle is unavailable without a public object."""

    async def _prime_without_camera() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_without_camera)

    await init_entry(hass, ufp, [doorbell])

    description = next(d for d in CAMERA_SWITCHES if d.key == "smart_person")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_switch_camera_detection_available_with_recording_disabled(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """A migrated detection toggle stays available with recording disabled.

    Unlike the legacy private-only switch, the public detection toggles no
    longer gate their availability on ``is_recording_enabled`` (breaking change).
    """

    doorbell.recording_settings.mode = RecordingMode.NEVER
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    description = next(d for d in CAMERA_SWITCHES if d.key == "smart_person")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_switch_camera_privacy(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Tests Privacy Mode switch for cameras with privacy mode defaulted on."""

    previous_mic = doorbell.mic_volume = 53
    previous_record = doorbell.recording_settings.mode = RecordingMode.DETECTIONS

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = PRIVACY_MODE_SWITCH

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )

    state = hass.states.get(entity_id)
    assert state and state.state == "off"
    assert ATTR_PREV_MIC not in state.attributes
    assert ATTR_PREV_RECORD not in state.attributes

    with patch_ufp_method(
        doorbell, "set_privacy", new_callable=AsyncMock
    ) as mock_set_privacy:
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_set_privacy.assert_called_with(True, 0, RecordingMode.NEVER)

        new_doorbell = doorbell.model_copy()
        new_doorbell.add_privacy_zone()
        new_doorbell.mic_volume = 0
        new_doorbell.recording_settings.mode = RecordingMode.NEVER
        ufp.api.bootstrap.cameras = {new_doorbell.id: new_doorbell}

        mock_msg = Mock()
        mock_msg.changed_data = {}
        mock_msg.new_obj = new_doorbell
        ufp.ws_msg(mock_msg)

        state = hass.states.get(entity_id)
        assert state and state.state == "on"
        assert state.attributes[ATTR_PREV_MIC] == previous_mic
        assert state.attributes[ATTR_PREV_RECORD] == previous_record.value

        mock_set_privacy.reset_mock()

        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_set_privacy.assert_called_with(False, previous_mic, previous_record)


async def test_switch_camera_privacy_already_on(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Tests Privacy Mode switch for cameras with privacy mode defaulted on."""

    doorbell.add_privacy_zone()
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.SWITCH, 17, 15)

    description = PRIVACY_MODE_SWITCH

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )

    with patch_ufp_method(
        doorbell, "set_privacy", new_callable=AsyncMock
    ) as mock_set_privacy:
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        mock_set_privacy.assert_called_once_with(False, 100, RecordingMode.ALWAYS)


async def test_switch_turn_on_client_error(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test switch turn on with ClientError raises HomeAssistantError."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    description = LIGHT_SWITCHES[1]

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, light, description
    )

    public = make_public_light(light)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with (
        patch.object(
            public,
            "set_status_light",
            new_callable=AsyncMock,
            side_effect=ClientError("Test error"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


async def test_switch_turn_on_not_authorized(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test switch turn on with NotAuthorized raises HomeAssistantError."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    description = LIGHT_SWITCHES[1]

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, light, description
    )

    public = make_public_light(light)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with (
        patch.object(
            public,
            "set_status_light",
            new_callable=AsyncMock,
            side_effect=NotAuthorized("Not authorized"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


# A USL Environmental reports these four and neither motion nor alarm-sound
# detection, so none of its capabilities back a motion or alarm switch.
_ENV_CAPABILITIES = {
    SensorFeatureCapability.TEMPERATURE,
    SensorFeatureCapability.HUMIDITY,
    SensorFeatureCapability.LIGHT,
    SensorFeatureCapability.WATER_LEAK,
}


async def test_switch_sense_capability_creation_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A capability map limits the config switches to the advertised capabilities."""
    setup_public_sensor(ufp, capabilities=_ENV_CAPABILITIES)
    await init_entry(hass, ufp, [sensor_all])

    for key, created in (
        ("status_light", True),
        ("temperature", True),
        ("humidity", True),
        ("light", True),
        ("motion", False),
        ("alarm", False),
    ):
        description = next(d for d in SENSE_SWITCHES if d.key == key)
        _, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, sensor_all, description
        )
        assert (entity_registry.async_get(entity_id) is not None) is created, key


async def test_switch_sense_capability_registry_cleanup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A console upgrade removes registry entries for unsupported capabilities."""
    stale = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{sensor_all.mac}_motion",
        config_entry=ufp.entry,
    )
    setup_public_sensor(ufp, capabilities=_ENV_CAPABILITIES)
    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(stale.entity_id) is None


async def test_switch_sense_no_capability_map_creates_all(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Without a capability map (Protect below 7.2) every config switch is created."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    for description in SENSE_SWITCHES:
        _, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, sensor_all, description
        )
        assert entity_registry.async_get(entity_id) is not None, description.key


async def test_switch_sense_no_capability_map_keeps_existing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Without a capability map (Protect below 7.2) nothing is removed.

    The console cannot say which capabilities it lacks, so an existing entity
    must survive setup instead of being deleted on a guess.
    """
    existing = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{sensor_all.mac}_motion",
        config_entry=ufp.entry,
    )
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(existing.entity_id) is not None


# The five sense settings the public API exposes, with the public-mock override
# that flips them and the public setter each switch must write through.
MIGRATED_SENSE_SWITCHES = [
    ("motion", "motion_enabled", "set_motion_status"),
    ("temperature", "temperature_enabled", "set_temperature_status"),
    ("humidity", "humidity_enabled", "set_humidity_status"),
    ("light", "light_enabled", "set_light_status"),
    ("alarm", "alarm_enabled", "set_alarm"),
]


@pytest.mark.parametrize(("key", "public_kwarg", "set_method"), MIGRATED_SENSE_SWITCHES)
async def test_switch_sense_public_value(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    key: str,
    public_kwarg: str,
    set_method: str,
) -> None:
    """Each migrated sense switch reads its state from the public object."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    description = next(d for d in SENSE_SWITCHES if d.key == key)
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, sensor_all, description
    )
    assert hass.states.get(entity_id).state == STATE_ON

    # every setting is enabled on the private fixture, so a public OFF can only
    # come from the public object
    public = make_public_sensor(sensor_all, **{public_kwarg: False})
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(("key", "public_kwarg", "set_method"), MIGRATED_SENSE_SWITCHES)
async def test_switch_sense_set_public(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
    key: str,
    public_kwarg: str,
    set_method: str,
) -> None:
    """Each migrated sense switch writes through the public API."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    description = next(d for d in SENSE_SWITCHES if d.key == key)
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, sensor_all, description
    )

    public = make_public_sensor(sensor_all)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(public, set_method, new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_method.assert_called_once_with(False)


async def test_switch_sense_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """A migrated sense switch is unavailable without a public object."""
    await init_entry(hass, ufp, [sensor_all])

    description = next(d for d in SENSE_SWITCHES if d.key == "motion")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, sensor_all, description
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_switch_sense_status_light_stays_private(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """The status light has no public counterpart, so it reads the private object.

    Unlike the migrated switches it must stay usable without a public object.
    """
    await init_entry(hass, ufp, [sensor_all])

    description = next(d for d in SENSE_SWITCHES if d.key == "status_light")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, sensor_all, description
    )
    assert hass.states.get(entity_id).state == STATE_ON

    with patch_ufp_method(
        sensor_all, "set_status_light", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_method.assert_called_once_with(False)


async def test_switch_sense_public_switches_ignore_local_permissions(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A read-only local user keeps the migrated switches but not the private one.

    The migrated switches write through the API key, so the local user's write
    bit must not gate them; the status light still uses a private setter and
    stays behind PermRequired.WRITE.
    """
    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict({"rawPermission": "sensor:read:*"})
    ]
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    for key, _public_kwarg, _set_method in MIGRATED_SENSE_SWITCHES:
        description = next(d for d in SENSE_SWITCHES if d.key == key)
        _, entity_id = await ids_from_device_description(
            hass, Platform.SWITCH, sensor_all, description
        )
        assert entity_registry.async_get(entity_id) is not None, key

    description = next(d for d in SENSE_SWITCHES if d.key == "status_light")
    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, sensor_all, description
    )
    assert entity_registry.async_get(entity_id) is None


_SMART_KEYS = {key for key, _, _ in CAMERA_SWITCHES_DETECTION_READ}


def _switch_keys(entity_registry: er.EntityRegistry, mac: str) -> set[str]:
    """Return the description keys of the switches registered for a device."""
    prefix = f"{mac}_"
    return {
        entry.unique_id.removeprefix(prefix)
        for entry in entity_registry.entities.values()
        if entry.domain == Platform.SWITCH and entry.unique_id.startswith(prefix)
    }


def _make_streamless_public_camera(camera: Camera) -> Mock:
    """Build a public camera without RTSPS streams (snapshot-only)."""
    public = make_public_camera(camera)
    public.rtsps_streams = None
    return public


@pytest.mark.parametrize(
    ("key", "object_types", "audio_types"), CAMERA_SWITCHES_DETECTION_READ
)
async def test_switch_camera_detection_capability_gating(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    key: str,
    object_types: list[SmartDetectObjectType],
    audio_types: list[SmartDetectAudioType],
) -> None:
    """A detection switch exists only for a capability the camera advertises."""
    doorbell.feature_flags.smart_detect_types = object_types
    doorbell.feature_flags.smart_detect_audio_types = audio_types
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    assert _switch_keys(entity_registry, doorbell.mac) & _SMART_KEYS == {key}


async def test_switch_command_when_public_object_vanishes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_all: Sensor,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A switch deleted mid-call raises a translated error, not AttributeError.

    Service calls filter unavailable entities once up front and then run the
    entity coroutines, so a delete frame landing after that check must not
    reach the command path as a missing public object.
    """
    public = make_public_sensor(
        sensor_all, capabilities={SensorFeatureCapability.MOTION}
    )
    pb = ufp_public_only.api.public_bootstrap
    pb.sensors = {public.id: public}

    await setup_public_only()
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{public.mac}_motion"
    )
    assert entity_id
    platform = next(
        p for p in async_get_platforms(hass, DOMAIN) if p.domain == Platform.SWITCH
    )
    entity = platform.entities[entity_id]
    request_call = entity.async_request_call

    async def _delete_then_run(coro: Coroutine[Any, Any, Any]) -> Any:
        """Drop the sensor after the availability filter, before the command."""
        pb.sensors.pop(public.id)
        msg = public_device_ws_message(public)
        msg.new_obj = None
        msg.old_obj = public
        ufp_public_only.devices_ws_subscription(msg)
        return await request_call(coro)

    with (
        patch.object(entity, "async_request_call", _delete_then_run),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    public.set_motion_status.assert_not_called()
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "device_not_available"
    assert err.value.translation_placeholders == {"device_name": public.display_name}


async def test_switch_hybrid_public_sensor_without_private_deferred(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Hybrid leaves a public sensor without a private object to the adopt path.

    It gets no entities from the public object alone, and the capability
    cleanup does not touch its registry entries either.
    """
    setup_public_sensor(ufp, capabilities=_ENV_CAPABILITIES)
    orphan = make_public_sensor(sensor_all, capabilities=_ENV_CAPABILITIES)
    orphan.id = "orphan-sensor"
    orphan.mac = "FFEEDDCCBB03"
    ufp.api.public_bootstrap.sensors[orphan.id] = orphan
    stale = entity_registry.async_get_or_create(
        Platform.SWITCH, DOMAIN, f"{orphan.mac}_motion", config_entry=ufp.entry
    )

    await init_entry(hass, ufp, [])

    assert _switch_keys(entity_registry, orphan.mac) == {"motion"}
    assert entity_registry.async_get(stale.entity_id) is not None


@pytest.mark.parametrize(
    ("fixture_name", "make", "key", "setter", "absent_keys"),
    [
        pytest.param(
            "doorbell",
            _make_streamless_public_camera,
            "smart_person",
            "set_person_detection",
            {"ssh", "motion", "high_fps", "privacy_mode", "color_night_vision"},
            id="camera",
        ),
        pytest.param(
            "sensor_all",
            partial(
                make_public_sensor,
                motion_enabled=True,
                capabilities={SensorFeatureCapability.MOTION},
            ),
            "motion",
            "set_motion_status",
            {"status_light", "temperature"},
            id="sensor",
        ),
        pytest.param(
            "light",
            partial(make_public_light, is_indicator_enabled=True),
            "status_light",
            "set_status_light",
            {"ssh"},
            id="light",
        ),
    ],
)
async def test_public_only_switch_end_to_end(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    fixture_name: str,
    make: Callable[[Any], Mock],
    key: str,
    setter: str,
    absent_keys: set[str],
) -> None:
    """A public-only entry builds the migrated switches from the public object.

    Private-only switches and the NVR switches are absent, the device is
    registered from public identity and commands go to the public setter.
    """
    device = request.getfixturevalue(fixture_name)
    public = make(device)
    store = getattr(ufp_public_only.api.public_bootstrap, f"{device.model.value}s")
    store[device.id] = public

    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    keys = _switch_keys(entity_registry, device.mac)
    assert key in keys
    assert not keys & absent_keys
    assert hass.states.get("switch.unifiprotect_insights_enabled") is None

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{device.mac}_{key}"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.model == public.type
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIFI_MAC), ufp_public_only.entry.entry_id
    )
    assert nvr_device
    assert device_entry.via_device_id == nvr_device.id

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    getattr(public, setter).assert_awaited_once_with(False)


async def test_public_only_switch_camera_capability_gating(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    doorbell: Camera,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Without a private object the detection switches gate on the public capability."""
    doorbell.feature_flags.smart_detect_types = [SmartDetectObjectType.PERSON]
    doorbell.feature_flags.smart_detect_audio_types = []
    public = _make_streamless_public_camera(doorbell)
    ufp_public_only.api.public_bootstrap.cameras[doorbell.id] = public

    await setup_public_only()

    assert _switch_keys(entity_registry, doorbell.mac) & _SMART_KEYS == {"smart_person"}


@pytest.mark.parametrize(
    ("fixture_name", "make", "key"),
    [
        pytest.param(
            "sensor_all",
            partial(make_public_sensor, capabilities={SensorFeatureCapability.MOTION}),
            "motion",
            id="sensor",
        ),
        pytest.param(
            "doorbell", _make_streamless_public_camera, "smart_person", id="camera"
        ),
    ],
)
async def test_public_only_switch_added_after_setup(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    entity_registry: er.EntityRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    caplog: pytest.LogCaptureFixture,
    fixture_name: str,
    make: Callable[[Any], Mock],
    key: str,
) -> None:
    """In public-only mode a device added later gets its switches from its add frame.

    The public devices websocket ``add`` frame is the only discovery signal
    without a local user; a re-delivered frame must not add a second time.
    """
    await setup_public_only()
    assert_entity_counts(hass, Platform.SWITCH, 0, 0)

    device = request.getfixturevalue(fixture_name)
    public = make(device)
    store = getattr(ufp_public_only.api.public_bootstrap, f"{device.model.value}s")
    store[device.id] = public
    msg = public_device_ws_message(public)
    msg.action = WSAction.ADD
    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert key in _switch_keys(entity_registry, device.mac)
    count = len(hass.states.async_entity_ids(Platform.SWITCH.value))

    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(Platform.SWITCH.value)) == count
    assert "already exists" not in caplog.text


async def test_public_only_switch_sense_registry_cleanup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_all: Sensor,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """The capability cleanup runs without a private bootstrap."""
    stale = entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{sensor_all.mac}_temperature",
        config_entry=ufp_public_only.entry,
    )
    ufp_public_only.api.public_bootstrap.sensors[sensor_all.id] = make_public_sensor(
        sensor_all, capabilities={SensorFeatureCapability.MOTION}
    )

    await setup_public_only()

    assert entity_registry.async_get(stale.entity_id) is None
