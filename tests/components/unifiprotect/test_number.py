"""Test the UniFi Protect number platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import (
    Camera,
    Chime,
    DeviceState,
    IRLEDMode,
    Light,
    RingSetting,
    Sensor,
)

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.number import (
    CAMERA_NUMBERS,
    LIGHT_NUMBERS,
    SENSE_NUMBERS,
    ProtectNumberEntityDescription,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import patch_ufp_method
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
    """Test sensitivity number entity for lights."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.NUMBER, 2, 2)

    description = LIGHT_NUMBERS[0]
    assert description.ufp_set_method is not None

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, light, description
    )

    with patch_ufp_method(
        light, "set_sensitivity", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            "number",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": 15.0},
            blocking=True,
        )

        mock_method.assert_called_once_with(15.0)


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

    with patch_ufp_method(
        light, "set_duration_public", new_callable=AsyncMock
    ) as mock_method:
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


@pytest.mark.parametrize("description", CAMERA_NUMBERS)
async def test_number_camera_simple(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera_all_features: Camera,
    description: ProtectNumberEntityDescription,
) -> None:
    """Tests simple numbers for cameras using the all features fixture."""
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


async def test_number_sense_sensitivity_set(
    hass: HomeAssistant, ufp: MockUFPFixture, sensor_all: Sensor
) -> None:
    """Setting the motion sensitivity calls the public API setter."""

    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.NUMBER, sensor_all, SENSE_NUMBERS[0]
    )

    with patch_ufp_method(
        sensor_all, "set_motion_sensitivity_public", new_callable=AsyncMock
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
