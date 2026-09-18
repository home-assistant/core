"""Test the UniFi Protect switch platform."""

from typing import Any
from unittest.mock import AsyncMock, Mock, call

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
from homeassistant.helpers import entity_registry as er

from . import patch_ufp_method
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

    with patch_ufp_method(
        light, "set_status_light_public", new_callable=AsyncMock
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


@pytest.mark.parametrize("description", CAMERA_SWITCHES_NO_EXTRA)
async def test_switch_camera_simple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    description: ProtectSwitchEntityDescription,
) -> None:
    """Tests all simple switches for cameras."""

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

    with patch_ufp_method(
        doorbell, "set_video_mode_public", new_callable=AsyncMock
    ) as mock_method:
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
    assert description.ufp_set_method.endswith("_public")

    _, entity_id = await ids_from_device_description(
        hass, Platform.SWITCH, doorbell, description
    )

    with patch_ufp_method(
        doorbell, description.ufp_set_method, new_callable=AsyncMock
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

    with (
        patch_ufp_method(
            light,
            "set_status_light_public",
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

    with (
        patch_ufp_method(
            light,
            "set_status_light_public",
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
    ("motion", "motion_enabled", "set_motion_status_public"),
    ("temperature", "temperature_enabled", "set_temperature_status_public"),
    ("humidity", "humidity_enabled", "set_humidity_status_public"),
    ("light", "light_enabled", "set_light_status_public"),
    ("alarm", "alarm_enabled", "set_alarm_public"),
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

    with patch_ufp_method(
        sensor_all, set_method, new_callable=AsyncMock
    ) as mock_method:
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
