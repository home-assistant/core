"""Test helpers for UniFi Protect."""

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from typing import Any
from unittest.mock import AsyncMock, Mock

from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from uiprotect import EventChange, ProtectApiClient, ProtectEvent
from uiprotect.anonymize import random_hex
from uiprotect.api import RTSPSStreams
from uiprotect.data import (
    Bootstrap,
    Camera,
    ChannelQuality,
    Chime,
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
    SmartDetectAudioType,
    SmartDetectObjectType,
    VideoMode,
    WSAction,
    WSSubscriptionMessage,
)
from uiprotect.data.bootstrap import ProtectDeviceRef
from uiprotect.data.public_devices import (
    PublicCamera,
    PublicCameraFeatureFlags,
    PublicCameraLedSettings,
    PublicChime,
    PublicDeviceModel,
    PublicHdrMode,
    PublicLcdMessage,
    PublicLight,
    PublicLightDeviceSettings,
    PublicLightModeSettings,
    PublicOsdSettings,
    PublicRingSettings,
    PublicSensor,
    PublicSensorAlarmSettingsRead,
    PublicSensorLeakSettings,
    PublicSensorMetric,
    PublicSensorMotionSettingsRead,
    PublicSensorStats,
    PublicSensorThresholdSettings,
    PublicSignalState,
    PublicSmartDetectSettings,
    PublicWirelessBatteryStatus,
    PublicWirelessConnectionState,
    SensorFeatureCapability,
)
from uiprotect.utils import to_js_time
from uiprotect.websocket import WebsocketState

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er, translation
from homeassistant.helpers.entity import EntityDescription
from homeassistant.util import dt as dt_util


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
    events_ws_state_subscription: Callable[[WebsocketState], None] | None = None
    public_resync_subscription: Callable[[bool], None] | None = None
    public_resync_unsub: Mock | None = None
    # Active RTSPS qualities the fake console reports, keyed by camera id.
    rtsps_qualities: dict[str, tuple[ChannelQuality, ...]] = field(default_factory=dict)

    def ws_msg(self, msg: WSSubscriptionMessage) -> None:
        """Emit WS message for testing."""

        if self.ws_subscription is not None:
            self.ws_subscription(msg)

    def events_msg(self, event: ProtectEvent, change: EventChange) -> None:
        """Emit a public-API events websocket message for testing."""

        if self.events_subscription is not None:
            self.events_subscription(event, change)

    def public_resync(
        self,
        added: Iterable[Any] = (),
        removed: Iterable[Any] = (),
        success: bool = True,
    ) -> None:
        """Emit the library's public reconnect resync for testing.

        Mirrors uiprotect: one synthetic add/remove devices websocket frame per
        device whose membership changed, then the resync completion callback.
        """
        assert self.devices_ws_subscription is not None
        assert self.public_resync_subscription is not None
        for obj in added:
            self.devices_ws_subscription(
                WSSubscriptionMessage(
                    action=WSAction.ADD,
                    new_update_id=obj.id,
                    changed_data={"modelKey": obj.model.value, "id": obj.id},
                    new_obj=obj,
                    old_obj=None,
                )
            )
        for obj in removed:
            self.devices_ws_subscription(
                WSSubscriptionMessage(
                    action=WSAction.REMOVE,
                    new_update_id=obj.id,
                    changed_data={"modelKey": obj.model.value, "id": obj.id},
                    new_obj=None,
                    old_obj=obj,
                )
            )
        self.public_resync_subscription(success)


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


def registered_keys(
    entity_registry: er.EntityRegistry, platform: Platform, mac: str
) -> set[str]:
    """Return the description keys registered for a device on a platform."""
    prefix = f"{mac}_"
    return {
        entry.unique_id.removeprefix(prefix)
        for entry in entity_registry.entities.values()
        if entry.domain == platform and entry.unique_id.startswith(prefix)
    }


def make_streamless_public_camera(camera: Camera, **kwargs: Any) -> Mock:
    """Build a public camera without RTSPS streams (snapshot-only)."""
    public = make_public_camera(camera, **kwargs)
    public.rtsps_streams = None
    return public


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
        old_id = device.id
        add_device(ufp.api.bootstrap, device, regenerate_ids)
        # Copies share their original's id until regenerated, so keep the old entry.
        if (qualities := ufp.rtsps_qualities.get(old_id)) is not None:
            ufp.rtsps_qualities[device.id] = qualities

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()


# The RTSPS URL the console reports for each active quality of a test camera.
_RTSPS_URLS: dict[ChannelQuality, str] = {
    ChannelQuality.HIGH: "rtsps://127.0.0.1:7441/test_high_alias?enableSrtp",
    ChannelQuality.MEDIUM: "rtsps://127.0.0.1:7441/test_medium_alias?enableSrtp",
    ChannelQuality.LOW: "rtsps://127.0.0.1:7441/test_low_alias?enableSrtp",
    ChannelQuality.PACKAGE: "rtsps://127.0.0.1:7441/test_package_alias?enableSrtp",
}


def set_active_rtsps_qualities(
    ufp: MockUFPFixture, camera: Camera, *qualities: ChannelQuality
) -> None:
    """Set the RTSPS qualities the console reports active for a test camera."""
    ufp.rtsps_qualities[camera.id] = qualities


def active_rtsps_qualities(
    rtsps_qualities: dict[str, tuple[ChannelQuality, ...]], camera_id: str
) -> tuple[ChannelQuality, ...]:
    """Return a test camera's active RTSPS qualities (only high by default)."""
    return rtsps_qualities.get(camera_id, (ChannelQuality.HIGH,))


def public_rtsps_for(*qualities: ChannelQuality) -> RTSPSStreams:
    """Build primed RTSPS streams with the given qualities active.

    Mirrors what the library writes onto ``PublicCamera.rtsps_streams`` during
    ``update_public()`` — only active qualities carry a URL. The server answers
    a successful read with ``null`` per inactive quality even when nothing is
    enabled, so a read always yields a streams object; ``None`` on the camera
    means the read itself failed (best-effort prime).
    """
    return RTSPSStreams(**{quality: _RTSPS_URLS[quality] for quality in qualities})


def bind_public_device_properties(public: Mock, model: type[PublicDeviceModel]) -> None:
    """Evaluate the model's own reachability and model name.

    A spec mock would otherwise return truthy mocks for these properties.
    """
    mock_type = type(public)
    mock_type.is_reachable = model.is_reachable
    mock_type.model_name = property(lambda obj: obj.type or model._MODEL_NAME)


_PUBLIC_STORE_ATTRS: dict[ModelType, str] = {
    ModelType.CAMERA: "cameras",
    ModelType.LIGHT: "lights",
    ModelType.SENSOR: "sensors",
    ModelType.CHIME: "chimes",
    ModelType.VIEWPORT: "viewers",
    ModelType.FOB: "fobs",
    ModelType.LINK_STATION: "alarm_hubs",
    ModelType.SIREN: "sirens",
    ModelType.RELAY: "relays",
}


def make_public_bootstrap(**attrs: Any) -> Mock:
    """Build a ``PublicBootstrap`` mock backed by per-family device maps.

    ``store_for``/``get``/``all_devices`` read the maps at call time, so a test
    may replace a whole map after setup (``pb.lights = {...}``).
    """
    pb = Mock(spec=PublicBootstrap)
    for attr in (
        *_PUBLIC_STORE_ATTRS.values(),
        "arm_profiles",
        "speakers",
        "link_stations",
        "bridges",
        "liveviews",
    ):
        setattr(pb, attr, {})
    pb.arm_mode = None
    pb.nvr = None
    for attr, value in attrs.items():
        setattr(pb, attr, value)

    def _store_for(model: ModelType) -> dict[str, Any] | None:
        if (attr := _PUBLIC_STORE_ATTRS.get(model)) is None:
            return None
        return getattr(pb, attr)

    def _get(model: ModelType, obj_id: str) -> Any:
        store = _store_for(model)
        return None if store is None else store.get(obj_id)

    def _all_devices(*, include_nvr: bool = False) -> Iterator[Any]:
        if include_nvr and pb.nvr is not None:
            yield pb.nvr
        for attr in _PUBLIC_STORE_ATTRS.values():
            yield from getattr(pb, attr).values()

    pb.store_for = Mock(side_effect=_store_for)
    pb.get = Mock(side_effect=_get)
    pb.all_devices = _all_devices
    pb.to_diagnostics = partial(PublicBootstrap.to_diagnostics, pb)
    # The real lookup, over the fake stores.
    pb.get_device_from_mac = partial(PublicBootstrap.get_device_from_mac, pb)
    return pb


def _mirror_on_update_public(
    ufp: MockUFPFixture,
    private_store_attr: str,
    store: dict[str, Any],
    make: Callable[[Any], Mock],
    *,
    keep_existing: bool = False,
) -> None:
    """Fill ``store`` from the private bootstrap whenever ``update_public`` runs.

    Mirrors the library prime so enumeration (which reads the store) sees the
    public objects; lookups keep mirroring lazily for devices adopted later.
    """
    previous = ufp.api.update_public

    async def _update_public(*args: Any, **kwargs: Any) -> Any:
        result = await previous(*args, **kwargs)
        for obj_id, private in getattr(ufp.api.bootstrap, private_store_attr).items():
            if keep_existing and obj_id in store:
                continue
            store[obj_id] = make(private)
        return result

    ufp.api.update_public = AsyncMock(side_effect=_update_public)


def make_public_sensor(
    sensor: Sensor,
    *,
    percentage: int = 10,
    is_low: bool = False,
    state: DeviceState | None = None,
    is_motion_detected: bool = False,
    motion_enabled: bool = True,
    motion_sensitivity: int = 100,
    temperature_enabled: bool = True,
    humidity_enabled: bool = True,
    light_enabled: bool = True,
    alarm_enabled: bool | None = None,
    mount_type: MountType | None = None,
    is_opened: bool = False,
    is_leak_detected: bool = False,
    is_tampering_detected: bool = False,
    capabilities: set[SensorFeatureCapability] | None = None,
    leak_internal_enabled: bool = False,
    leak_external_enabled: bool = False,
    light_value: float = 10.0,
    humidity_value: float = 10.0,
    temperature_value: float = 10.0,
    open_status_changed_at: datetime | None = None,
    motion_detected_at: datetime | None = None,
    tampering_detected_at: datetime | None = None,
    signal_strength: int | None = None,
    signal_quality: int | None = None,
) -> Mock:
    """Build a public-API sensor for a private sensor.

    Real ``wireless_connection_state`` / ``motion_settings`` / ``leak_settings``
    models back the migrated value paths so a wrong ``ufp_public_value`` path
    fails the test; identifiers come from the (synthetic) private sensor fixture,
    never from real capture data. Identity, state, mount type and alarm
    enablement mirror the private sensor; the other values default to those of
    the ``sensor_all`` fixture (every metric enabled, nothing detected, 10%
    battery, readings of 10.0). Each ``*`` override lets a test diverge. The
    mount-derived enablement properties are computed from the resolved mount
    type so a ``mount_type`` override stays consistent. ``capabilities`` is the
    sensor's capability map; ``None`` (the default) advertises every capability.
    """
    public = Mock(spec=PublicSensor)
    bind_public_device_properties(public, PublicSensor)
    public.id = sensor.id
    public.mac = sensor.mac
    public.name = sensor.name
    public.display_name = sensor.display_name
    public.type = sensor.type
    public.model = ModelType.SENSOR
    public.state = DeviceState[sensor.state.name] if state is None else state
    public.mount_type = sensor.mount_type if mount_type is None else mount_type
    public.is_opened = is_opened
    public.is_leak_detected = is_leak_detected
    public.is_tampering_detected = is_tampering_detected
    caps = set(SensorFeatureCapability) if capabilities is None else capabilities
    public.supports = Mock(side_effect=lambda capability: capability in caps)
    public.leak_settings = PublicSensorLeakSettings(
        is_internal_enabled=leak_internal_enabled,
        is_external_enabled=leak_external_enabled,
    )
    public.is_motion_detected = is_motion_detected
    public.motion_settings = PublicSensorMotionSettingsRead(
        is_enabled=motion_enabled, sensitivity=motion_sensitivity
    )
    public.temperature_settings = PublicSensorThresholdSettings(
        is_enabled=temperature_enabled
    )
    public.humidity_settings = PublicSensorThresholdSettings(
        is_enabled=humidity_enabled
    )
    public.light_settings = PublicSensorThresholdSettings(is_enabled=light_enabled)
    public.alarm_settings = PublicSensorAlarmSettingsRead(
        is_enabled=(
            sensor.alarm_settings.is_enabled if alarm_enabled is None else alarm_enabled
        )
    )
    public.wireless_connection_state = PublicWirelessConnectionState(
        battery_status=PublicWirelessBatteryStatus(
            percentage=percentage, is_low=is_low
        ),
        # Signal strength as in the sensor fixture.
        signal_state=PublicSignalState(
            signal_strength=-50 if signal_strength is None else signal_strength,
            signal_quality=signal_quality,
        ),
    )
    # The metrics default to the same number, so a test that has to tell the
    # value paths apart passes its own.
    public.stats = PublicSensorStats(
        light=PublicSensorMetric(value=light_value),
        humidity=PublicSensorMetric(value=humidity_value),
        temperature=PublicSensorMetric(value=temperature_value),
    )
    # The public API reports these as a JS epoch; a test asserting one of them
    # passes its own instant.
    public.open_status_changed_at = to_js_time(open_status_changed_at)
    public.motion_detected_at = to_js_time(motion_detected_at)
    public.tampering_detected_at = to_js_time(tampering_detected_at)
    # Mocks do not evaluate properties, so derive them with the library's own
    # logic: a wrong assumption about what gates a metric, or about how the
    # epoch fields convert, fails the test.
    for name in (
        "is_contact_sensor_enabled",
        "is_leak_sensor_enabled",
        "is_leak_detection_enabled",
        "is_motion_sensor_enabled",
        "is_alarm_sensor_enabled",
        "is_temperature_sensor_enabled",
        "is_humidity_sensor_enabled",
        "is_light_sensor_enabled",
        "open_status_changed_at_dt",
        "motion_detected_at_dt",
        "tampering_detected_at_dt",
    ):
        setattr(public, name, getattr(PublicSensor, name).fget(public))
    return public


def make_public_light(
    light: Light,
    *,
    state: DeviceState | None = None,
    is_light_on: bool = False,
    is_dark: bool | None = None,
    is_pir_motion_detected: bool = False,
    last_motion_ms: int | None = None,
    led_level: int | None = None,
    pir_duration_ms: int | None = None,
    pir_sensitivity: int = 45,
    is_indicator_enabled: bool = False,
    light_mode: LightModeType = LightModeType.MOTION,
    light_mode_enable_at: LightModeEnableType | None = None,
) -> Mock:
    """Build a public-API light for a private light.

    Identity, state, darkness and last motion mirror the private light; the
    other fields the FloodLight entities read over the public API default to
    the light fixture's values. Each ``*`` override lets a test set a value the
    private object would not produce, proving the entity reads the public
    source. The public API reports ``pir_duration`` and ``last_motion`` in
    milliseconds.
    """
    public = Mock(spec=PublicLight)
    bind_public_device_properties(public, PublicLight)
    public.id = light.id
    public.mac = light.mac
    public.name = light.name
    public.display_name = light.display_name
    public.type = light.type
    public.model = ModelType.LIGHT
    public.state = DeviceState[light.state.name] if state is None else state
    public.is_light_on = is_light_on
    public.is_dark = light.is_dark if is_dark is None else is_dark
    public.is_pir_motion_detected = is_pir_motion_detected
    if last_motion_ms is not None:
        public.last_motion = last_motion_ms
    elif light.last_motion is not None:
        public.last_motion = round(light.last_motion.timestamp() * 1000)
    else:
        public.last_motion = None
    public.light_mode_settings = PublicLightModeSettings(
        mode=light_mode,
        # The light fixture enables the mode at all times.
        enable_at=(
            LightModeEnableType.ALWAYS
            if light_mode_enable_at is None
            else light_mode_enable_at
        ),
    )
    public.light_device_settings = PublicLightDeviceSettings(
        is_indicator_enabled=is_indicator_enabled,
        # LED level and PIR duration as in the light fixture.
        led_level=6 if led_level is None else led_level,
        pir_duration=45000 if pir_duration_ms is None else pir_duration_ms,
        pir_sensitivity=pir_sensitivity,
    )
    public.last_motion_dt = PublicLight.last_motion_dt.fget(public)
    type(public).light_mode_preset = PublicLight.light_mode_preset
    return public


_ALL_OBJECT_TYPES = [t for t in SmartDetectObjectType if t.audio_type is None]
_ALL_AUDIO_TYPES = list(SmartDetectAudioType)


def make_public_camera(
    camera: Camera,
    *,
    state: DeviceState | None = None,
    status_light: bool = False,
    osd_name: bool = False,
    osd_date: bool = False,
    osd_logo: bool = False,
    osd_debug: bool = False,
    video_mode: VideoMode | None = None,
    is_motion_detected: bool = False,
    is_smart_currently_detected: bool = False,
    is_person_currently_detected: bool = False,
    is_vehicle_currently_detected: bool = False,
    is_animal_currently_detected: bool = False,
    is_audio_currently_detected: bool = False,
    is_smoke_currently_detected: bool = False,
    is_cmonx_currently_detected: bool = False,
    is_siren_currently_detected: bool = False,
    is_baby_cry_currently_detected: bool = False,
    is_speaking_currently_detected: bool = False,
    is_bark_currently_detected: bool = False,
    is_car_alarm_currently_detected: bool = False,
    is_car_horn_currently_detected: bool = False,
    is_glass_break_currently_detected: bool = False,
    object_types: list[SmartDetectObjectType] | None = None,
    audio_types: list[SmartDetectAudioType] | None = None,
    mic_volume: int | None = None,
    is_mic_enabled: bool = True,
    hdr_type: PublicHdrMode | None = None,
    lcd_message: PublicLcdMessage | None = None,
    active_patrol_slot: int | None = None,
) -> Mock:
    """Build a public-API camera for a private camera's migrated fields.

    The stream tiers/mic/HDR back the migrated stream and select entities; the
    ``is_*`` flags back the migrated ``ufp_public_value`` detection paths and the
    ``smart_detect_settings`` types back the per-type ``ufp_public_enabled_fn``
    gates (default: all types enabled). ``state`` and ``mic_volume`` mirror the
    private camera when not overridden, ``video_mode`` and ``hdr_type``
    default to the fixture's default mode and HDR off.

    ``status_light`` and the ``osd_*`` flags deliberately default to off instead
    of mirroring, so a test overriding one sets a value the private object would
    not produce and a wrong ``ufp_public_value``/``ufp_public_value_fn`` fails
    the test. ``lcd_message`` defaults to none for the same reason.
    """
    public = Mock(spec=PublicCamera)
    bind_public_device_properties(public, PublicCamera)
    public.id = camera.id
    public.mac = camera.mac
    public.name = camera.name
    public.display_name = camera.display_name
    public.type = camera.type
    public.model = ModelType.CAMERA
    public.state = DeviceState[camera.state.name] if state is None else state
    public.led_settings = PublicCameraLedSettings(is_enabled=status_light)
    public.osd_settings = PublicOsdSettings(
        is_name_enabled=osd_name,
        is_date_enabled=osd_date,
        is_logo_enabled=osd_logo,
        is_debug_enabled=osd_debug,
    )
    public.video_mode = VideoMode.DEFAULT if video_mode is None else video_mode
    public.mic_volume = camera.mic_volume if mic_volume is None else mic_volume
    public.is_mic_enabled = is_mic_enabled
    public.lcd_message = lcd_message
    public.lcd_message_text = PublicCamera.lcd_message_text.fget(public)
    # The doorbell text falls back to the default message of the private NVR.
    public.api = camera._api
    public.active_patrol_slot = active_patrol_slot
    public.is_motion_detected = is_motion_detected
    public.is_smart_currently_detected = is_smart_currently_detected
    public.is_person_currently_detected = is_person_currently_detected
    public.is_vehicle_currently_detected = is_vehicle_currently_detected
    public.is_animal_currently_detected = is_animal_currently_detected
    public.is_audio_currently_detected = is_audio_currently_detected
    public.is_smoke_currently_detected = is_smoke_currently_detected
    public.is_cmonx_currently_detected = is_cmonx_currently_detected
    public.is_siren_currently_detected = is_siren_currently_detected
    public.is_baby_cry_currently_detected = is_baby_cry_currently_detected
    public.is_speaking_currently_detected = is_speaking_currently_detected
    public.is_bark_currently_detected = is_bark_currently_detected
    public.is_car_alarm_currently_detected = is_car_alarm_currently_detected
    public.is_car_horn_currently_detected = is_car_horn_currently_detected
    public.is_glass_break_currently_detected = is_glass_break_currently_detected
    public.smart_detect_settings = PublicSmartDetectSettings(
        object_types=_ALL_OBJECT_TYPES if object_types is None else object_types,
        audio_types=_ALL_AUDIO_TYPES if audio_types is None else audio_types,
    )
    # A Mock(spec) does not evaluate properties, so mirror the PublicCamera
    # parity properties the migrated switches read and the detection sensors
    # gate on, using the library's own logic.
    for name in (
        "is_high_fps_enabled",
        "is_person_detection_on",
        "is_vehicle_detection_on",
        "is_animal_detection_on",
        "is_package_detection_on",
        "is_license_plate_detection_on",
        "is_smoke_detection_on",
        "is_co_detection_on",
        "is_siren_detection_on",
        "is_baby_cry_detection_on",
        "is_speaking_detection_on",
        "is_bark_detection_on",
        "is_car_alarm_detection_on",
        "is_car_horn_detection_on",
        "is_glass_break_detection_on",
    ):
        setattr(public, name, getattr(PublicCamera, name).fget(public))
    public.hdr_type = PublicHdrMode.OFF if hdr_type is None else hdr_type
    public.hdr_mode_display = PublicCamera.hdr_mode_display.fget(public)
    flags = camera.feature_flags
    # The doorbell fixture appends the package channel (id 3).
    public.has_package_camera = any(c.id == 3 for c in camera.channels)
    # Spec'd so a private-only flag reads as absent.
    public.feature_flags = Mock(spec=PublicCameraFeatureFlags)
    public.feature_flags.support_full_hd_snapshot = False
    public.feature_flags.has_hdr = flags.has_hdr
    public.feature_flags.has_mic = flags.has_mic
    public.feature_flags.has_led_status = flags.has_led_status
    public.feature_flags.has_speaker = flags.has_speaker
    public.has_speaker = flags.has_speaker
    # No talkback stream until a test starts one.
    public.talkback_stream = None
    public.feature_flags.video_modes = list(flags.video_modes)
    public.feature_flags.smart_detect_types = list(flags.smart_detect_types)
    public.feature_flags.smart_detect_audio_types = list(
        flags.smart_detect_audio_types or []
    )
    # Derived from the mirrored video modes with the library's own logic.
    public.feature_flags.has_highfps = PublicCameraFeatureFlags.has_highfps.fget(
        public.feature_flags
    )
    # The capability gate runs the library's own logic on the mirrored flags.
    public.can_detect = Mock(side_effect=partial(PublicCamera.can_detect, public))
    qualities = [ChannelQuality.HIGH, ChannelQuality.MEDIUM, ChannelQuality.LOW]
    if public.has_package_camera:
        qualities.append(ChannelQuality.PACKAGE)
    public.hardware_stream_qualities.return_value = qualities
    return public


def setup_public_sensor(
    ufp: MockUFPFixture,
    capabilities: set[SensorFeatureCapability] | None = None,
    **mirror_overrides: Any,
) -> None:
    """Expose private sensors over the public API via a real ``PublicBootstrap``.

    Lookups go through the real ``PublicBootstrap.get``; the mirror resolves
    against the private bootstrap at call time, so it is robust to ``init_entry``
    regenerating device ids. ``capabilities`` is forwarded to the mirror as the
    sensor's capability map. Further keyword arguments are handed
    to ``make_public_sensor``, so a test can diverge a mirrored value.
    """
    public_bootstrap = PublicBootstrap()
    pb = make_public_bootstrap(sensors=public_bootstrap.sensors)
    make = partial(make_public_sensor, capabilities=capabilities, **mirror_overrides)

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        if (
            model is ModelType.SENSOR
            and (private := ufp.api.bootstrap.sensors.get(obj_id)) is not None
        ):
            public_bootstrap.sensors[obj_id] = make(private)
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    _mirror_on_update_public(ufp, "sensors", public_bootstrap.sensors, make)
    ufp.api.has_public_bootstrap = True
    # Keep the fixture's public NVR (identity and doorbell settings).
    pb.nvr = ufp.api.public_bootstrap.nvr
    ufp.api.public_bootstrap = pb


def setup_public_light(ufp: MockUFPFixture, **mirror_overrides: Any) -> None:
    """Expose private lights over the public API via a real ``PublicBootstrap``.

    Mirrors ``setup_public_sensor`` for ``ModelType.LIGHT`` so the migrated
    FloodLight duration number reads from the public object. Keyword arguments
    are handed to ``make_public_light``.
    """
    public_bootstrap = PublicBootstrap()
    pb = make_public_bootstrap(lights=public_bootstrap.lights)
    make = partial(make_public_light, **mirror_overrides)

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        # One mock per id so command assertions hit the entity's cached object.
        if (
            model is ModelType.LIGHT
            and obj_id not in public_bootstrap.lights
            and (private := ufp.api.bootstrap.lights.get(obj_id)) is not None
        ):
            public_bootstrap.lights[obj_id] = make(private)
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    _mirror_on_update_public(
        ufp, "lights", public_bootstrap.lights, make, keep_existing=True
    )
    ufp.api.has_public_bootstrap = True
    # Keep the fixture's public NVR (identity and doorbell settings).
    pb.nvr = ufp.api.public_bootstrap.nvr
    ufp.api.public_bootstrap = pb


def setup_public_camera(ufp: MockUFPFixture, **public_overrides: Any) -> None:
    """Expose private cameras over the public API via a real ``PublicBootstrap``.

    Mirrors ``setup_public_sensor`` for ``ModelType.CAMERA`` so the migrated
    camera config entities read from the public object. Keyword arguments are
    handed to ``make_public_camera``.
    """
    public_bootstrap = PublicBootstrap()
    pb = make_public_bootstrap(cameras=public_bootstrap.cameras)
    make = partial(make_public_camera, **public_overrides)

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        if (
            model is ModelType.CAMERA
            and (private := ufp.api.bootstrap.cameras.get(obj_id)) is not None
        ):
            public_bootstrap.cameras[obj_id] = make(private)
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    ufp.api.has_public_bootstrap = True
    # Keep the fixture's public NVR (identity and doorbell settings).
    pb.nvr = ufp.api.public_bootstrap.nvr
    ufp.api.public_bootstrap = pb


def make_public_chime(
    chime: Chime,
    *,
    state: DeviceState | None = None,
    ring_settings: list[PublicRingSettings] | None = None,
) -> Mock:
    """Build a public-API chime with the given ring settings."""
    public = Mock(spec=PublicChime)
    bind_public_device_properties(public, PublicChime)
    public.id = chime.id
    public.mac = chime.mac
    public.name = chime.name
    public.display_name = chime.display_name
    public.type = chime.type
    public.model = ModelType.CHIME
    public.state = DeviceState[chime.state.name] if state is None else state
    public.ring_settings = [] if ring_settings is None else ring_settings
    # The real lookup, over the mock's ring settings.
    public.get_ring_setting = partial(PublicChime.get_ring_setting, public)
    return public


def setup_public_chime(
    ufp: MockUFPFixture, ring_settings: list[PublicRingSettings] | None = None
) -> None:
    """Expose private chimes over the public API via a real ``PublicBootstrap``.

    Mirrors ``setup_public_light`` for ``ModelType.CHIME`` so the ring volume
    numbers read from the public object.
    """
    public_bootstrap = PublicBootstrap()
    pb = make_public_bootstrap(chimes=public_bootstrap.chimes)
    make = partial(make_public_chime, ring_settings=ring_settings)

    def _get(model: ModelType, obj_id: str) -> ProtectModelWithId | None:
        # One mock per id so command assertions hit the entity's cached object.
        if (
            model is ModelType.CHIME
            and obj_id not in public_bootstrap.chimes
            and (private := ufp.api.bootstrap.chimes.get(obj_id)) is not None
        ):
            public_bootstrap.chimes[obj_id] = make(private)
        return public_bootstrap.get(model, obj_id)

    pb.get = _get
    _mirror_on_update_public(
        ufp, "chimes", public_bootstrap.chimes, make, keep_existing=True
    )
    ufp.api.has_public_bootstrap = True
    # Keep the fixture's public NVR (identity and doorbell settings).
    pb.nvr = ufp.api.public_bootstrap.nvr
    ufp.api.public_bootstrap = pb


def public_device_ws_message(
    public_obj: Mock,
    *,
    action: WSAction = WSAction.UPDATE,
    changed_data: dict[str, Any] | None = None,
) -> Mock:
    """Build a public devices WS message carrying a public object."""
    msg = Mock()
    msg.action = action
    msg.changed_data = changed_data or {}
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
