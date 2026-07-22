"""Test helpers for UniFi Protect."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import Mock

from uiprotect import EventChange, ProtectApiClient, ProtectEvent
from uiprotect.api import RTSPSStreams
from uiprotect.data import (
    Bootstrap,
    Camera,
    ChannelQuality,
    DeviceState,
    Event,
    EventType,
    Light,
    LightModeEnableType,
    LightModeType,
    ModelType,
    MountType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
    PublicBootstrap,
    Sensor,
    WSSubscriptionMessage,
)
from uiprotect.data.bootstrap import ProtectDeviceRef
from uiprotect.data.public_devices import (
    PublicCamera,
    PublicHdrMode,
    PublicLight,
    PublicLightDeviceSettings,
    PublicLightModeSettings,
    PublicSensor,
    PublicSensorLeakSettings,
    PublicSensorMotionSettingsRead,
    PublicWirelessBatteryStatus,
    PublicWirelessConnectionState,
    SensorFeatureCapability,
)
from uiprotect.test_util.anonymize import random_hex
from uiprotect.websocket import WebsocketState

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er, translation
from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@dataclass
class MockUFPFixture:
    """Mock for NVR."""

    entry: MockConfigEntry
    api: ProtectApiClient
    ws_subscription: Callable[[WSSubscriptionMessage], None] | None = None
    ws_state_subscription: Callable[[WebsocketState], None] | None = None
    devices_ws_subscription: Callable[[WSSubscriptionMessage], None] | None = None
    events_subscription: Callable[[ProtectEvent, EventChange], None] | None = None
    devices_ws_state_subscription: Callable[[WebsocketState], None] | None = None

    def ws_msg(self, msg: WSSubscriptionMessage) -> None:
        """Emit WS message for testing."""

        if self.ws_subscription is not None:
            self.ws_subscription(msg)

    def events_msg(self, event: ProtectEvent, change: EventChange) -> None:
        """Emit a public-API events websocket message for testing."""

        if self.events_subscription is not None:
            self.events_subscription(event, change)


def reset_objects(bootstrap: Bootstrap):
    """Reset bootstrap objects."""

    bootstrap.cameras = {}
    bootstrap.lights = {}
    bootstrap.sensors = {}
    bootstrap.viewers = {}
    bootstrap.events = {}
    bootstrap.chimes = {}


async def time_changed(hass: HomeAssistant, seconds: int) -> None:
    """Trigger time changed."""
    next_update = dt_util.utcnow() + timedelta(seconds)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()


async def enable_entity(
    hass: HomeAssistant, entry_id: str, entity_id: str
) -> er.RegistryEntry:
    """Enable a disabled entity."""
    entity_registry = er.async_get(hass)

    updated_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not updated_entity.disabled
    await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()

    return updated_entity


def assert_entity_counts(
    hass: HomeAssistant, platform: Platform, total: int, enabled: int
) -> None:
    """Assert entity counts for a given platform."""

    entity_registry = er.async_get(hass)

    entities = [
        e for e in entity_registry.entities if split_entity_id(e)[0] == platform.value
    ]

    assert len(entities) == total
    assert len(hass.states.async_all(platform.value)) == enabled


def normalize_name(name: str) -> str:
    """Normalize name."""

    return name.lower().replace(":", "").replace(" ", "_").replace("-", "_")


async def async_get_translated_entity_name(
    hass: HomeAssistant, platform: Platform, translation_key: str
) -> str:
    """Get the translated entity name for a given platform and translation key."""
    platform_name = "unifiprotect"

    # Get the translations for the UniFi Protect integration
    translations = await translation.async_get_translations(
        hass, "en", "entity", {platform_name}
    )

    # Build the translation key in the format that Home Assistant uses
    # component.{integration}.entity.{platform}.{translation_key}.name
    full_translation_key = (
        f"component.{platform_name}.entity.{platform.value}.{translation_key}.name"
    )

    # Get the translated name, fall back to the translation key if not found
    return translations.get(full_translation_key, translation_key)


async def ids_from_device_description(
    hass: HomeAssistant,
    platform: Platform,
    device: ProtectAdoptableDeviceModel,
    description: EntityDescription,
) -> tuple[str, str]:
    """Return expected unique_id and entity_id using HA translation logic."""

    entity_name = normalize_name(device.display_name)

    if getattr(description, "translation_key", None):
        # Get the actual translated name from Home Assistant
        translated_name = await async_get_translated_entity_name(
            hass, platform, description.translation_key
        )
        description_entity_name = normalize_name(translated_name)
    elif getattr(description, "device_class", None):
        description_entity_name = normalize_name(description.device_class)
    else:
        description_entity_name = normalize_name(description.key)

    unique_id = f"{device.mac}_{description.key}"
    entity_id = f"{platform.value}.{entity_name}_{description_entity_name}"

    return unique_id, entity_id


def generate_random_ids() -> tuple[str, str]:
    """Generate random IDs for device."""

    return random_hex(24).lower(), random_hex(12).upper()


def regenerate_device_ids(device: ProtectAdoptableDeviceModel) -> None:
    """Regenerate the IDs on UFP device."""

    device.id, device.mac = generate_random_ids()


def add_device_ref(bootstrap: Bootstrap, device: ProtectAdoptableDeviceModel) -> None:
    """Manually add device ref to bootstrap for lookup."""

    ref = ProtectDeviceRef(id=device.id, model=device.model)
    bootstrap.id_lookup[device.id] = ref
    bootstrap.mac_lookup[device.mac.lower()] = ref


def add_device(
    bootstrap: Bootstrap, device: ProtectAdoptableDeviceModel, regenerate_ids: bool
) -> None:
    """Add test device to bootstrap."""

    if device.model is None:
        return

    device._api = bootstrap.api
    if isinstance(device, Camera) and device.model is ModelType.CAMERA:
        for channel in device.channels:
            channel._api = bootstrap.api

    if regenerate_ids:
        regenerate_device_ids(device)

    devices = getattr(bootstrap, f"{device.model.value}s")
    devices[device.id] = device
    add_device_ref(bootstrap, device)


async def init_entry(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    devices: Sequence[ProtectAdoptableDeviceModel],
    regenerate_ids: bool = True,
) -> None:
    """Initialize Protect entry with given devices."""

    reset_objects(ufp.api.bootstrap)
    for device in devices:
        add_device(ufp.api.bootstrap, device, regenerate_ids)

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()


def public_rtsps_for(camera: Camera) -> RTSPSStreams | None:
    """Build a camera's primed RTSPS streams from its RTSP-enabled channels.

    Mirrors what the library writes onto ``PublicCamera.rtsps_streams`` during
    ``update_public()`` — only RTSP-enabled channels carry an active URL, and a
    camera with none is left streamless (``None``).
    """
    urls = {
        channel.rtsps_quality: channel.rtsps_url
        for channel in camera.channels
        if channel.is_rtsp_enabled and channel.rtsps_quality is not None
    }
    return RTSPSStreams(**urls) if urls else None


def make_public_sensor(
    sensor: Sensor,
    *,
    percentage: int | None = None,
    is_low: bool | None = None,
    state: DeviceState | None = None,
    is_motion_detected: bool | None = None,
    motion_enabled: bool | None = None,
    motion_sensitivity: int | None = None,
    mount_type: MountType | None = None,
    is_opened: bool | None = None,
    is_leak_detected: bool | None = None,
    is_tampering_detected: bool | None = None,
    capabilities: set[SensorFeatureCapability] | None = None,
    leak_internal_enabled: bool = False,
    leak_external_enabled: bool = False,
) -> Mock:
    """Build a public-API sensor mirroring a private sensor's migrated fields.

    Real ``wireless_connection_state`` / ``motion_settings`` / ``leak_settings``
    models back the migrated value paths so a wrong ``ufp_public_value`` path
    fails the test; identifiers come from the (synthetic) private sensor fixture,
    never from real capture data. Each ``*`` override lets a test diverge from
    the private value. The mount-derived enablement properties are computed from
    the resolved mount type so a ``mount_type`` override stays consistent.
    ``capabilities`` mimics the capability map of newer firmware; ``None`` (the
    default) models older firmware without a map, where every entity is created.
    """
    public = Mock(spec=PublicSensor)
    public.id = sensor.id
    public.mac = sensor.mac
    public.model = ModelType.SENSOR
    public.state = DeviceState[sensor.state.name] if state is None else state
    public.mount_type = sensor.mount_type if mount_type is None else mount_type
    public.is_contact_sensor_enabled = public.mount_type in {
        MountType.DOOR,
        MountType.WINDOW,
        MountType.GARAGE,
    }
    public.is_leak_sensor_enabled = public.mount_type is MountType.LEAK
    public.is_opened = sensor.is_opened if is_opened is None else is_opened
    public.is_leak_detected = (
        sensor.is_leak_detected if is_leak_detected is None else is_leak_detected
    )
    public.is_tampering_detected = (
        sensor.is_tampering_detected
        if is_tampering_detected is None
        else is_tampering_detected
    )
    public.has_feature_flags = capabilities is not None
    public.supports = Mock(
        side_effect=lambda capability: (
            capabilities is not None and capability in capabilities
        )
    )
    public.leak_settings = PublicSensorLeakSettings(
        is_internal_enabled=leak_internal_enabled,
        is_external_enabled=leak_external_enabled,
    )
    public.is_motion_detected = (
        sensor.is_motion_detected if is_motion_detected is None else is_motion_detected
    )
    public.motion_settings = PublicSensorMotionSettingsRead(
        is_enabled=(
            sensor.motion_settings.is_enabled
            if motion_enabled is None
            else motion_enabled
        ),
        sensitivity=(
            sensor.motion_settings.sensitivity
            if motion_sensitivity is None
            else motion_sensitivity
        ),
    )
    public.wireless_connection_state = PublicWirelessConnectionState(
        battery_status=PublicWirelessBatteryStatus(
            percentage=(
                sensor.battery_status.percentage if percentage is None else percentage
            ),
            is_low=sensor.battery_status.is_low if is_low is None else is_low,
        )
    )
    return public


def make_public_light(
    light: Light,
    *,
    state: DeviceState | None = None,
    is_light_on: bool | None = None,
    is_dark: bool | None = None,
    is_pir_motion_detected: bool | None = None,
    last_motion_ms: int | None = None,
    led_level: int | None = None,
    pir_duration_ms: int | None = None,
    pir_sensitivity: int | None = None,
    is_indicator_enabled: bool | None = None,
    light_mode: LightModeType | None = None,
    light_mode_enable_at: LightModeEnableType | None = None,
) -> Mock:
    """Build a public-API light mirroring the private fixture's migrated fields.

    Every field the FloodLight entities read over the public API is mirrored from
    the private light; each ``*`` override lets a test set a value the private
    object would not produce, proving the entity reads the public source. The
    public API reports ``pir_duration`` and ``last_motion`` in milliseconds.
    """
    lds = light.light_device_settings
    lms = light.light_mode_settings
    public = Mock(spec=PublicLight)
    public.id = light.id
    public.mac = light.mac
    public.model = ModelType.LIGHT
    public.state = DeviceState[light.state.name] if state is None else state
    public.is_light_on = light.is_light_on if is_light_on is None else is_light_on
    public.is_dark = light.is_dark if is_dark is None else is_dark
    public.is_pir_motion_detected = (
        light.is_pir_motion_detected
        if is_pir_motion_detected is None
        else is_pir_motion_detected
    )
    if last_motion_ms is not None:
        public.last_motion = last_motion_ms
    elif light.last_motion is not None:
        public.last_motion = round(light.last_motion.timestamp() * 1000)
    else:
        public.last_motion = None
    public.light_mode_settings = PublicLightModeSettings(
        mode=lms.mode if light_mode is None else light_mode,
        enable_at=(
            lms.enable_at if light_mode_enable_at is None else light_mode_enable_at
        ),
    )
    public.light_device_settings = PublicLightDeviceSettings(
        is_indicator_enabled=(
            lds.is_indicator_enabled
            if is_indicator_enabled is None
            else is_indicator_enabled
        ),
        led_level=lds.led_level if led_level is None else led_level,
        pir_duration=(
            round(lds.pir_duration.total_seconds() * 1000)
            if pir_duration_ms is None
            else pir_duration_ms
        ),
        pir_sensitivity=(
            lds.pir_sensitivity if pir_sensitivity is None else pir_sensitivity
        ),
    )
    return public


_HDR_DISPLAY_TO_PUBLIC = {
    "auto": PublicHdrMode.AUTO,
    "always": PublicHdrMode.ON,
    "off": PublicHdrMode.OFF,
}


def make_public_camera(
    camera: Camera,
    *,
    state: DeviceState | None = None,
    mic_volume: int | None = None,
    hdr_type: PublicHdrMode | None = None,
) -> Mock:
    """Build a public-API camera mirroring a private camera's migrated fields.

    ``mic_volume`` and ``hdr_type`` default to values derived from the private
    fixture so the public mirror matches it; pass an override to assert a value
    the private object would not produce.
    """
    public = Mock(spec=PublicCamera)
    public.id = camera.id
    public.mac = camera.mac
    public.name = camera.name
    public.display_name = camera.display_name
    public.type = camera.type
    public.model = ModelType.CAMERA
    public.state = DeviceState[camera.state.name] if state is None else state
    public.mic_volume = camera.mic_volume if mic_volume is None else mic_volume
    public.hdr_type = (
        _HDR_DISPLAY_TO_PUBLIC[camera.hdr_mode_display]
        if hdr_type is None
        else hdr_type
    )
    public.has_package_camera = camera.feature_flags.has_package_camera
    public.feature_flags = Mock()
    public.feature_flags.support_full_hd_snapshot = (
        camera.feature_flags.support_full_hd_snapshot
    )
    qualities = [ChannelQuality.HIGH, ChannelQuality.MEDIUM, ChannelQuality.LOW]
    if public.has_package_camera:
        qualities.append(ChannelQuality.PACKAGE)
    public.hardware_stream_qualities.return_value = qualities
    return public


def setup_public_sensor(
    ufp: MockUFPFixture,
    capabilities: set[SensorFeatureCapability] | None = None,
) -> None:
    """Expose private sensors over the public API via a real ``PublicBootstrap``.

    Lookups go through the real ``PublicBootstrap.get``; the mirror resolves
    against the private bootstrap at call time, so it is robust to ``init_entry``
    regenerating device ids. ``capabilities`` is forwarded to the mirror to model
    newer firmware with a capability map.
    """
    public_bootstrap = PublicBootstrap()
    pb = Mock(spec=PublicBootstrap)
    pb.sensors = public_bootstrap.sensors
    pb.relays = {}
    pb.sirens = {}
    pb.arm_mode = None
    pb.arm_profiles = {}

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        if (
            model is ModelType.SENSOR
            and (private := ufp.api.bootstrap.sensors.get(obj_id)) is not None
        ):
            public_bootstrap.sensors[obj_id] = make_public_sensor(
                private, capabilities=capabilities
            )
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb


def setup_public_light(ufp: MockUFPFixture) -> None:
    """Expose private lights over the public API via a real ``PublicBootstrap``.

    Mirrors ``setup_public_sensor`` for ``ModelType.LIGHT`` so the migrated
    FloodLight duration number reads from the public object.
    """
    public_bootstrap = PublicBootstrap()
    pb = Mock(spec=PublicBootstrap)
    pb.lights = public_bootstrap.lights
    pb.relays = {}
    pb.sirens = {}
    pb.arm_mode = None
    pb.arm_profiles = {}

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        if (
            model is ModelType.LIGHT
            and (private := ufp.api.bootstrap.lights.get(obj_id)) is not None
        ):
            public_bootstrap.lights[obj_id] = make_public_light(private)
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb


def setup_public_camera(ufp: MockUFPFixture) -> None:
    """Expose private cameras over the public API via a real ``PublicBootstrap``.

    Mirrors ``setup_public_sensor`` for ``ModelType.CAMERA`` so the migrated
    camera config entities read from the public object.
    """
    public_bootstrap = PublicBootstrap()
    pb = Mock(spec=PublicBootstrap)
    pb.cameras = public_bootstrap.cameras
    pb.relays = {}
    pb.sirens = {}
    pb.arm_mode = None
    pb.arm_profiles = {}

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        if (
            model is ModelType.CAMERA
            and (private := ufp.api.bootstrap.cameras.get(obj_id)) is not None
        ):
            public_bootstrap.cameras[obj_id] = make_public_camera(private)
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = pb


def public_device_ws_message(public_obj: Mock) -> Mock:
    """Build a public devices WS message carrying a public object."""
    msg = Mock()
    msg.changed_data = {}
    msg.old_obj = None
    msg.new_obj = public_obj
    return msg


async def remove_entities(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    ufp_devices: list[ProtectAdoptableDeviceModel],
) -> None:
    """Remove all entities for given Protect devices."""

    for ufp_device in ufp_devices:
        if not ufp_device.is_adopted_by_us:
            continue

        devices = getattr(ufp.api.bootstrap, f"{ufp_device.model.value}s")
        del devices[ufp_device.id]

        mock_msg = Mock()
        mock_msg.changed_data = {}
        mock_msg.old_obj = ufp_device
        mock_msg.new_obj = None
        ufp.ws_msg(mock_msg)

    await time_changed(hass, 30)


async def adopt_devices(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    ufp_devices: list[ProtectAdoptableDeviceModel],
    fully_adopt: bool = False,
):
    """Emit WS to re-adopt give Protect devices."""

    for ufp_device in ufp_devices:
        if fully_adopt:
            ufp_device.is_adopted = True
            ufp_device.is_adopted_by_other = False
            ufp_device.can_adopt = False

        devices = getattr(ufp.api.bootstrap, f"{ufp_device.model.value}s")
        devices[ufp_device.id] = ufp_device
        # Add to id_lookup so get_device_from_id works
        add_device_ref(ufp.api.bootstrap, ufp_device)

        mock_msg = Mock()
        mock_msg.changed_data = {}
        mock_msg.new_obj = Event(
            api=ufp_device.api,
            id=random_hex(24),
            smart_detect_types=[],
            smart_detect_event_ids=[],
            type=EventType.DEVICE_ADOPTED,
            start=dt_util.utcnow(),
            score=100,
            metadata={"device_id": ufp_device.id},
            model=ModelType.EVENT,
        )
        ufp.ws_msg(mock_msg)

    await hass.async_block_till_done()
