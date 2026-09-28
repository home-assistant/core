"""Test the UniFi Protect number platform."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect.data import (
    Camera,
    Chime,
    DeviceState,
    IRLEDMode,
    Light,
    Permission,
    ProtectAdoptableDeviceModel,
    RingSetting,
    Sensor,
    WSAction,
)
from uiprotect.data.devices import Hotplug
from uiprotect.data.public_devices import PublicChime, SensorFeatureCapability

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION, DOMAIN
from homeassistant.components.unifiprotect.number import (
    CAMERA_NUMBERS,
    LIGHT_NUMBERS,
    SENSE_NUMBERS,
    ProtectNumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import patch_ufp_method
from .conftest import UNIFI_MAC
from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
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


async def test_number_sensor_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    await init_entry(hass, ufp, [camera, unadopted_camera])
    assert_entity_counts(hass, Platform.NUMBER, 4, 4)
    await remove_entities(hass, ufp, [camera, unadopted_camera])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)
    await adopt_devices(hass, ufp, [camera, unadopted_camera])
    assert_entity_counts(hass, Platform.NUMBER, 4, 4)


async def test_number_sensor_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)


async def test_number_setup_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """Test number entity setup for light devices."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    for description in LIGHT_NUMBERS:
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.NUMBER, light, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "45"
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_number_setup_camera_all(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test number entity setup for camera devices (all features)."""

    camera.feature_flags.has_chime = True
    camera.chime_duration = timedelta(seconds=1)
    camera.feature_flags.has_led_ir = True
    camera.isp_settings.icr_custom_value = 1
    camera.isp_settings.ir_led_mode = IRLEDMode.CUSTOM
    camera.feature_flags.has_speaker = True
    camera.speaker_settings.volume = 1
    camera.feature_flags.is_doorbell = True
    camera.speaker_settings.ring_volume = 1
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 7, 7)

    for description in CAMERA_NUMBERS:
        unique_id, entity_id = await ids_from_device_description(
            hass, Platform.NUMBER, camera, description
        )

        entity = entity_registry.async_get(entity_id)
        assert entity
        assert entity.unique_id == unique_id

        state = hass.states.get(entity_id)
        assert state
        assert state.state == "1"
        assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_number_setup_camera_none(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Test number entity setup for camera devices (no features)."""

    camera.feature_flags.can_optical_zoom = False
    camera.feature_flags.has_mic = False
    # has_wdr is an the inverse of has HDR
    camera.feature_flags.has_hdr = True
    camera.feature_flags.has_led_ir = False

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


async def test_number_no_mic_level_for_hot_plugged_mic(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """A camera whose only microphone is hot-plugged gets no microphone level.

    ``Camera.has_mic`` counts the hot-plugged module, but the public setter the
    number writes through refuses such a camera, so the built-in flag gates it.
    """
    camera.feature_flags.has_mic = False
    camera.feature_flags.hotplug = Hotplug(audio=True)
    assert camera.has_mic

    await init_entry(hass, ufp, [camera])

    assert "mic_level" not in _number_keys(entity_registry, camera.mac)


async def test_number_setup_camera_missing_attr(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Test number entity setup for camera devices (no features, bad attrs)."""

    camera.feature_flags = None

    await init_entry(hass, ufp, [camera])
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


async def test_number_light_sensitivity(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test sensitivity number entity for lights (public API)."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    description = LIGHT_NUMBERS[0]
    assert description.ufp_set_method is not None

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, description
    )

    public = make_public_light(light)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(public, "set_sensitivity", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 15.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(15.0)


async def test_number_light_sensitivity_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Sensitivity reads from the public object and refreshes on a public WS update."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, LIGHT_NUMBERS[0]
    )

    # A value the private fixture (45) would not produce proves the public source.
    public = make_public_light(light, pir_sensitivity=30)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "30"


async def test_number_light_sensitivity_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """The migrated sensitivity number is unavailable without a public object."""

    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, LIGHT_NUMBERS[0]
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_number_light_duration(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test auto-shutoff duration number entity for lights (public API)."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    description = LIGHT_NUMBERS[1]

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, description
    )

    public = make_public_light(light)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(public, "set_duration", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 15.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(timedelta(seconds=15.0))


async def test_number_light_duration_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Duration reads from the public object (ms) and refreshes on a public WS update."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, LIGHT_NUMBERS[1]
    )

    # A public value the private fixture (45 s) would not produce proves the source.
    public = make_public_light(light, pir_duration_ms=30000)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "30"


async def test_number_light_duration_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """The migrated duration number is unavailable without a public object."""

    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, LIGHT_NUMBERS[1]
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_number_light_duration_unavailable_on_public_disconnect(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Duration availability follows the public object's connection state."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, LIGHT_NUMBERS[1]
    )
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    public = make_public_light(light, state=DeviceState.DISCONNECTED)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_number_light_duration_none(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """A light that does not report a public duration leaves the number unknown."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, LIGHT_NUMBERS[1]
    )

    public = make_public_light(light)
    public.light_device_settings.pir_duration = None
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "description", [d for d in CAMERA_NUMBERS if not d.is_public_value]
)
async def test_number_camera_simple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera_all_features: Camera,
    description: ProtectNumberEntityDescription,
) -> None:
    """Tests the private-API numbers for cameras using the all features fixture."""
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [camera_all_features])
    assert_entity_counts(hass, Platform.NUMBER, 7, 7)

    assert description.ufp_set_method is not None

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, camera_all_features, description
    )

    with patch_ufp_method(
        camera_all_features, description.ufp_set_method, new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 1.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(1.0)


async def test_number_camera_mic_volume_set(
    hass: HomeAssistant, ufp: MockUFPFixture, camera_all_features: Camera
) -> None:
    """The migrated mic volume number writes through the public object."""
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [camera_all_features])

    description = next(d for d in CAMERA_NUMBERS if d.key == "mic_level")
    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, camera_all_features, description
    )

    public = make_public_camera(camera_all_features)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(public, "set_mic_volume", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 1.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(1.0)


async def test_number_camera_mic_volume_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Mic volume reads from the public object and refreshes on a public WS update."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [camera])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, camera, CAMERA_NUMBERS[1]
    )

    # A public value the private fixture (1) would not produce proves the source.
    public = make_public_camera(camera, mic_volume=42)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "42"


async def test_number_camera_mic_volume_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """The migrated mic volume number is unavailable without a public object."""

    # The default fixture mirrors every camera into the public bootstrap;
    # prime it empty to model a camera the public API does not know yet.
    async def _prime_empty() -> Mock:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_empty)
    await init_entry(hass, ufp, [camera])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, camera, CAMERA_NUMBERS[1]
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_number_camera_mic_volume_unavailable_on_public_disconnect(
    hass: HomeAssistant, ufp: MockUFPFixture, camera: Camera
) -> None:
    """Mic volume availability follows the public object's connection state."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [camera])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, camera, CAMERA_NUMBERS[1]
    )
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    public = make_public_camera(camera, state=DeviceState.DISCONNECTED)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_number_sense_sensitivity_public_value(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Motion sensitivity reads from the public object and refreshes on a WS update."""

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, sensor_all, SENSE_NUMBERS[0]
    )

    # A public value the private fixture (100) would not produce proves the source.
    public = make_public_sensor(sensor_all, motion_sensitivity=42)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "42"


async def test_number_sense_sensitivity_ignores_local_permissions(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A read-only local user keeps the motion sensitivity number.

    It writes through the API key, so the local user's write bit must not gate it.
    Its read-only mirror stays until the deprecation runs out.
    """
    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict({"rawPermission": "sensor:read:*"})
    ]
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, sensor_all, SENSE_NUMBERS[0]
    )
    assert entity_registry.async_get(entity_id) is not None
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{sensor_all.mac}_sensitivity"
        )
        is not None
    )


async def test_number_sense_sensitivity_set(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Setting the motion sensitivity calls the public API setter."""

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, sensor_all, SENSE_NUMBERS[0]
    )

    public = make_public_sensor(sensor_all)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(
        public, "set_motion_sensitivity", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 60.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(60.0)


async def test_number_sense_sensitivity_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """The migrated motion sensitivity number is unavailable without a public object."""

    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, sensor_all, SENSE_NUMBERS[0]
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_number_sense_sensitivity_unavailable_on_public_disconnect(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Motion sensitivity availability follows the public object's connection state."""

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, sensor_all, SENSE_NUMBERS[0]
    )
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    public = make_public_sensor(sensor_all, state=DeviceState.DISCONNECTED)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


def _setup_chime_with_doorbell(
    chime: Chime, doorbell: Camera, volume: int = 50
) -> None:
    """Set up chime with paired doorbell for testing."""
    chime.camera_ids = [doorbell.id]
    chime.ring_settings = [
        RingSetting(
            camera_id=doorbell.id,
            repeat_times=1,
            ringtone_id="test-ringtone-id",
            volume=volume,
        )
    ]


async def test_chime_ring_volume_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test chime ring volume number entity setup."""
    _setup_chime_with_doorbell(chime, doorbell, volume=75)

    await init_entry(hass, ufp, [chime, doorbell], regenerate_ids=False)

    entity_id = "number.test_chime_ring_volume_test_camera"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    assert entity.unique_id == f"{chime.mac}_ring_volume_{doorbell.id}"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "75"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_chime_ring_volume_set_value(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test setting chime ring volume."""
    _setup_chime_with_doorbell(chime, doorbell)

    await init_entry(hass, ufp, [chime, doorbell], regenerate_ids=False)

    entity_id = "number.test_chime_ring_volume_test_camera"

    with patch_ufp_method(
        chime, "set_volume_for_camera_public", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 80.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(doorbell, 80)


async def test_chime_volume_set_value(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test setting overall chime volume calls public ring-settings API."""
    _setup_chime_with_doorbell(chime, doorbell, volume=40)

    await init_entry(hass, ufp, [chime, doorbell], regenerate_ids=False)

    entity_id = "number.test_chime_volume"

    with patch_ufp_method(
        chime, "set_ring_settings_public", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 75.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(
            [
                {
                    "cameraId": doorbell.id,
                    "volume": 75,
                    "repeatTimes": 1,
                    "ringtoneId": "test-ringtone-id",
                }
            ]
        )


async def test_chime_ring_volume_multiple_cameras(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test chime ring volume with multiple paired cameras."""
    doorbell2 = doorbell.model_copy()
    doorbell2.id = "test-doorbell-2"
    doorbell2.name = "Test Doorbell 2"
    doorbell2.mac = "aa:bb:cc:dd:ee:02"

    chime.camera_ids = [doorbell.id, doorbell2.id]
    chime.ring_settings = [
        RingSetting(
            camera_id=doorbell.id,
            repeat_times=1,
            ringtone_id="test-ringtone-id",
            volume=60,
        ),
        RingSetting(
            camera_id=doorbell2.id,
            repeat_times=2,
            ringtone_id="test-ringtone-id-2",
            volume=80,
        ),
    ]

    await init_entry(hass, ufp, [chime, doorbell, doorbell2], regenerate_ids=False)

    state1 = hass.states.get("number.test_chime_ring_volume_test_camera")
    assert state1 is not None
    assert state1.state == "60"

    state2 = hass.states.get("number.test_chime_ring_volume_test_doorbell_2")
    assert state2 is not None
    assert state2.state == "80"


async def test_chime_ring_volume_unavailable_when_unpaired(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test chime ring volume becomes unavailable when camera is unpaired."""
    _setup_chime_with_doorbell(chime, doorbell)

    await init_entry(hass, ufp, [chime, doorbell], regenerate_ids=False)

    entity_id = "number.test_chime_ring_volume_test_camera"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "50"

    # Simulate removing the camera pairing
    new_chime = chime.model_copy()
    new_chime.ring_settings = []

    ufp.api.bootstrap.chimes = {new_chime.id: new_chime}
    ufp.api.bootstrap.nvr.system_info.ustorage = None
    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_chime

    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


def _number_keys(entity_registry: er.EntityRegistry, mac: str) -> set[str]:
    """Return the description keys of the numbers registered for a device."""
    prefix = f"{mac}_"
    return {
        entry.unique_id.removeprefix(prefix)
        for entry in entity_registry.entities.values()
        if entry.domain == Platform.NUMBER and entry.unique_id.startswith(prefix)
    }


def _make_streamless_public_camera(camera: Camera, **kwargs: Any) -> Mock:
    """Build a public camera without RTSPS streams (snapshot-only)."""
    public = make_public_camera(camera, **kwargs)
    public.rtsps_streams = None
    return public


@pytest.mark.parametrize(
    ("fixture_name", "make", "key", "value", "setter", "present_keys", "absent_keys"),
    [
        pytest.param(
            "camera",
            partial(_make_streamless_public_camera, mic_volume=42),
            "mic_level",
            "42",
            "set_mic_volume",
            set(),
            {"wdr_value", "zoom_position", "chime_duration", "icr_lux"},
            id="camera",
        ),
        pytest.param(
            "doorbell",
            partial(_make_streamless_public_camera, mic_volume=42),
            "mic_level",
            "42",
            "set_mic_volume",
            set(),
            {"system_sounds_volume", "doorbell_ring_volume", "chime_duration"},
            id="doorbell",
        ),
        pytest.param(
            "light",
            partial(make_public_light, pir_sensitivity=30),
            "sensitivity",
            "30",
            "set_sensitivity",
            {"duration"},
            set(),
            id="light",
        ),
        pytest.param(
            "sensor_all",
            partial(
                make_public_sensor,
                motion_sensitivity=42,
                capabilities={SensorFeatureCapability.MOTION},
            ),
            "sensitivity",
            "42",
            "set_motion_sensitivity",
            set(),
            set(),
            id="sensor",
        ),
    ],
)
async def test_public_only_number_end_to_end(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    fixture_name: str,
    make: Callable[[ProtectAdoptableDeviceModel], Mock],
    key: str,
    value: str,
    setter: str,
    present_keys: set[str],
    absent_keys: set[str],
) -> None:
    """A public-only entry builds the migrated numbers from the public object.

    Private-only numbers are absent, the device is registered from public
    identity and a new value goes to the public setter.
    """
    device = request.getfixturevalue(fixture_name)
    public = make(device)
    store = getattr(ufp_public_only.api.public_bootstrap, f"{device.model.value}s")
    store[device.id] = public

    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    keys = _number_keys(entity_registry, device.mac)
    assert key in keys
    assert present_keys <= keys
    assert not keys & absent_keys

    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{device.mac}_{key}"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == value

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
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 55}, blocking=True
    )
    getattr(public, setter).assert_awaited_once_with(55.0)


async def test_public_only_number_light_duration_setter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """The auto-shutoff duration is written as a timedelta to the public light."""
    public = make_public_light(light, pir_duration_ms=30000)
    ufp_public_only.api.public_bootstrap.lights[light.id] = public

    await setup_public_only()

    entity_id = entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{light.mac}_duration"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == "30"

    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: entity_id, "value": 45}, blocking=True
    )
    public.set_duration.assert_awaited_once_with(timedelta(seconds=45))


async def test_public_only_number_chime_has_no_numbers(
    hass: HomeAssistant,
    chime: Chime,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Chime volumes are private-only settings, so a public chime yields nothing."""
    public = Mock(spec=PublicChime)
    public.id = chime.id
    public.mac = chime.mac
    public.name = chime.name
    public.model = chime.model
    public.state = DeviceState.CONNECTED
    ufp_public_only.api.public_bootstrap.chimes[chime.id] = public

    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)


def _make_public_camera_without_mic(camera: Camera) -> Mock:
    """Build a public camera whose feature flags carry no built-in microphone."""
    public = _make_streamless_public_camera(camera)
    public.feature_flags.has_mic = False
    return public


@pytest.mark.parametrize(
    ("fixture_name", "make"),
    [
        pytest.param(
            "camera", _make_public_camera_without_mic, id="camera_without_mic"
        ),
        pytest.param(
            "sensor_all",
            partial(
                make_public_sensor, capabilities={SensorFeatureCapability.TEMPERATURE}
            ),
            id="sensor_without_motion",
        ),
    ],
)
async def test_public_only_number_gated_out(
    request: pytest.FixtureRequest,
    entity_registry: er.EntityRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    fixture_name: str,
    make: Callable[[ProtectAdoptableDeviceModel], Mock],
) -> None:
    """A device failing the public gate gets no number.

    The camera gate is the built-in microphone flag, the sense gate the
    motion capability.
    """
    device = request.getfixturevalue(fixture_name)
    store = getattr(ufp_public_only.api.public_bootstrap, f"{device.model.value}s")
    store[device.id] = make(device)

    await setup_public_only()

    assert _number_keys(entity_registry, device.mac) == set()


async def test_public_only_number_added_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """In public-only mode a light added later gets its numbers from its add frame.

    The public devices websocket ``add`` frame is the only discovery signal
    without a local user; a re-delivered frame must not add a second time.
    """
    await setup_public_only()
    assert_entity_counts(hass, Platform.NUMBER, 0, 0)

    public = make_public_light(light)
    ufp_public_only.api.public_bootstrap.lights[light.id] = public
    msg = public_device_ws_message(public)
    msg.action = WSAction.ADD
    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert _number_keys(entity_registry, light.mac) == {
        "sensitivity",
        "duration",
    }
    count = len(hass.states.async_entity_ids(Platform.NUMBER.value))

    ufp_public_only.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(Platform.NUMBER.value)) == count
    assert "already exists" not in caplog.text


async def test_public_only_number_sense_registry_cleanup(
    entity_registry: er.EntityRegistry,
    sensor_all: Sensor,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """The capability cleanup runs without a private bootstrap."""
    stale = entity_registry.async_get_or_create(
        Platform.NUMBER,
        DOMAIN,
        f"{sensor_all.mac}_sensitivity",
        config_entry=ufp_public_only.entry,
    )
    ufp_public_only.api.public_bootstrap.sensors[sensor_all.id] = make_public_sensor(
        sensor_all, capabilities={SensorFeatureCapability.TEMPERATURE}
    )

    await setup_public_only()

    assert entity_registry.async_get(stale.entity_id) is None
