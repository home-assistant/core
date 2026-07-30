"""Test helpers for the lifx integration."""

from typing import Any, TypeVar, cast
from unittest.mock import AsyncMock, MagicMock

from lifx import (
    HSBK,
    CeilingLight,
    CeilingLightState,
    CollectionInfo,
    DeviceCapabilities,
    FirmwareEffect,
    FirmwareInfo,
    HevConfig,
    HevCycleState,
    HevLight,
    HevLightState,
    InfraredLight,
    InfraredLightState,
    Light,
    LightLastHevCycleResult,
    LightState,
    LightWaveform,
    MatrixLight,
    MatrixLightState,
    MultiZoneLight,
    MultiZoneLightState,
    TileInfo,
    WifiInfo,
)

from homeassistant.components.lifx.const import DOMAIN
from homeassistant.components.lifx.light import LIFX_MIN_COLOR_RAMP
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.helpers import entity_registry as er

IP_ADDRESS = "127.0.0.1"
SERIAL = "d073d5ddeecc"
# The colon separated serial written by releases that treated it as a MAC
LEGACY_SERIAL = "d0:73:d5:dd:ee:cc"
MAC_ADDRESS = "d0:73:d5:dd:ee:cc"
LABEL = "My Bulb"
GROUP = "My Group"
INFRARED_SELECT_ENTITY_ID = "select.my_group_my_bulb_infrared_brightness"
INFRARED_NUMBER_ENTITY_ID = "number.my_group_my_bulb_infrared_brightness"

type MockDevice = (
    Light | MultiZoneLight | MatrixLight | CeilingLight | HevLight | InfraredLight
)
type MockState = (
    LightState
    | MultiZoneLightState
    | MatrixLightState
    | CeilingLightState
    | HevLightState
    | InfraredLightState
)

_DeviceT = TypeVar("_DeviceT", bound=MockDevice)
_StateT = TypeVar("_StateT", bound=MockState)


def register_legacy_infrared_select(
    entity_registry: er.EntityRegistry,
    disabled_by: er.RegistryEntryDisabler | None = None,
) -> None:
    """Register the infrared select an upgraded installation already has."""
    entity_registry.async_get_or_create(
        SELECT_DOMAIN,
        DOMAIN,
        f"{SERIAL}_infrared_brightness",
        suggested_object_id="my_group_my_bulb_infrared_brightness",
        disabled_by=disabled_by,
        # A registry entry written by an earlier run already carries the name
        original_name="Infrared brightness",
        has_entity_name=True,
    )


def assert_color_written(
    device: MockDevice,
    color: HSBK,
    *,
    period: float = LIFX_MIN_COLOR_RAMP,
    hue: bool = True,
    saturation: bool = True,
    brightness: bool = True,
    kelvin: bool = True,
) -> None:
    """Assert only the color components a service call named were written."""
    device.set_waveform_optional.assert_awaited_once_with(
        color,
        period=period,
        cycles=1,
        waveform=LightWaveform.HALF_SINE,
        transient=False,
        set_hue=hue,
        set_saturation=saturation,
        set_brightness=brightness,
        set_kelvin=kelvin,
    )


def _create_mock_state(
    state_type: type[_StateT],
    *,
    serial: str = SERIAL,
    mac_address: str = MAC_ADDRESS,
    **type_specific: Any,
) -> _StateT:
    """Create deterministic typed public state."""
    host_firmware = FirmwareInfo(build=0, version_major=4, version_minor=0)
    return state_type(
        model="LIFX Original 1000",
        label=LABEL,
        serial=serial,
        mac_address=mac_address,
        capabilities=DeviceCapabilities(
            has_color=True,
            has_multizone=False,
            has_chain=False,
            has_matrix=False,
            has_infrared=False,
            has_hev=False,
            has_extended_multizone=False,
            kelvin_min=2500,
            kelvin_max=9000,
        ),
        power=0,
        host_firmware=host_firmware,
        wifi_firmware=FirmwareInfo(build=0, version_major=4, version_minor=0),
        # The signal is only read while the RSSI sensor is enabled, but the
        # unit the firmware reports in is always resolved
        wifi_info=WifiInfo(signal=None, host_firmware=host_firmware),
        location=CollectionInfo(
            uuid="00000000000000000000000000000001",
            label="My Location",
            updated_at=0,
        ),
        group=CollectionInfo(
            uuid="00000000000000000000000000000002", label=GROUP, updated_at=0
        ),
        last_updated=0.0,
        color=HSBK(0.0, 0.0, 1.0, 3500),
        **type_specific,
    )


def _create_mock_device(
    device_type: type[_DeviceT], state: _StateT, *, ip: str = IP_ADDRESS
) -> _DeviceT:
    """Create a deterministic typed public device double."""
    device = MagicMock(spec=device_type(serial=state.serial, ip=ip))
    device.ip = ip
    device.serial = state.serial
    device.state = state
    device.refresh_state = AsyncMock()
    device.close = AsyncMock()
    device.set_power = AsyncMock()
    device.set_color = AsyncMock()
    device.set_waveform_optional = AsyncMock()
    device.set_reboot = AsyncMock()
    device.apply_theme = AsyncMock()
    # The library only reads the signal strength once it is switched on
    device.fetch_wifi_info = False
    return cast(_DeviceT, device)


def create_mock_light_state(
    *,
    serial: str = SERIAL,
    mac_address: str = MAC_ADDRESS,
) -> LightState:
    """Create deterministic refreshed light state."""
    return _create_mock_state(LightState, serial=serial, mac_address=mac_address)


def create_mock_light(
    *,
    ip: str = IP_ADDRESS,
    serial: str = SERIAL,
    mac_address: str = MAC_ADDRESS,
) -> Light:
    """Create a deterministic double of the public lifx-async boundary."""
    state = create_mock_light_state(serial=serial, mac_address=mac_address)

    return _create_mock_device(Light, state, ip=ip)


def create_mock_hev_light() -> HevLight:
    """Create a deterministic HEV light double."""
    state = _create_mock_state(
        HevLightState,
        hev_cycle=HevCycleState(duration_s=7200, remaining_s=30, last_power=False),
        hev_config=HevConfig(indication=False, duration_s=7200),
        hev_result=LightLastHevCycleResult.SUCCESS,
    )
    state.capabilities.has_hev = True
    device = _create_mock_device(HevLight, state)
    device.set_hev_cycle = AsyncMock()
    return device


def create_mock_infrared_light() -> InfraredLight:
    """Create a deterministic infrared light double."""
    state = _create_mock_state(InfraredLightState, infrared=1.0)
    state.capabilities.has_infrared = True
    device = _create_mock_device(InfraredLight, state)
    device.set_infrared = AsyncMock()
    return device


def create_mock_multizone_light(*, extended: bool = True) -> MultiZoneLight:
    """Create a deterministic multizone light double."""
    zones = [HSBK(300.0, 1.0, 1.0, 3500), HSBK(255.0, 1.0, 1.0, 3500)]
    state = _create_mock_state(
        MultiZoneLightState,
        zones=zones,
        zone_count=len(zones),
        effect=FirmwareEffect.OFF,
    )
    state.capabilities.has_multizone = True
    state.capabilities.has_extended_multizone = extended
    device = _create_mock_device(MultiZoneLight, state)
    device.set_all_color_zones = AsyncMock()
    return device


def _create_mock_tile(
    *,
    tile_index: int = 0,
    product: int = 55,
    width: int = 8,
    user_x: float = 0.0,
) -> TileInfo:
    """Create deterministic public tile metadata."""
    return TileInfo(
        tile_index=tile_index,
        accel_meas_x=0,
        accel_meas_y=0,
        accel_meas_z=0,
        user_x=user_x,
        user_y=0.0,
        width=width,
        height=8,
        supported_frame_buffers=0,
        device_version_vendor=1,
        device_version_product=product,
        device_version_version=0,
        firmware_build=0,
        firmware_version_minor=70,
        firmware_version_major=3,
    )


def create_mock_matrix_light() -> MatrixLight:
    """Create a deterministic matrix light double."""
    tile_colors = [HSBK(0.0, 0.0, 1.0, 3500)] * 64
    state = _create_mock_state(
        MatrixLightState,
        chain=[_create_mock_tile()],
        tile_orientations={0: "Right Side Up"},
        tile_colors=tile_colors,
        tile_count=1,
        effect=FirmwareEffect.OFF,
    )
    state.capabilities.has_matrix = True
    state.capabilities.has_chain = True
    device = _create_mock_device(MatrixLight, state)
    device.set_matrix_colors = AsyncMock()
    return device


def create_mock_ceiling_light() -> CeilingLight:
    """Create a deterministic ceiling light double."""
    downlight_colors = [HSBK(0.0, 0.0, 1.0, 3500)] * 64
    state = _create_mock_state(
        CeilingLightState,
        chain=[_create_mock_tile()],
        tile_orientations={0: "Right Side Up"},
        tile_colors=downlight_colors,
        tile_count=1,
        effect=FirmwareEffect.OFF,
        uplight_color=HSBK(0.0, 0.0, 1.0, 3500),
        downlight_colors=downlight_colors,
        uplight_is_on=False,
        downlight_is_on=False,
        uplight_zone=64,
        downlight_zones=slice(0, 64),
    )
    state.model = "LIFX Ceiling"
    state.capabilities.has_matrix = True
    state.capabilities.has_chain = True
    device = _create_mock_device(CeilingLight, state)
    device.set_matrix_colors = AsyncMock()
    return device


def _apply_reference_common(
    state: MockState,
    *,
    model: str,
    color: HSBK,
    kelvin_min: int,
    kelvin_max: int,
    firmware: tuple[int, int] = (3, 70),
) -> None:
    """Apply normalized fields captured from the released emulator."""
    state.model = model
    state.power = 65535
    state.color = color
    state.host_firmware = FirmwareInfo(0, *firmware)
    state.wifi_firmware = FirmwareInfo(0, *firmware)
    state.capabilities.kelvin_min = kelvin_min
    state.capabilities.kelvin_max = kelvin_max


def create_reference_color_light() -> Light:
    """Create the normalized released-emulator color light."""
    device = create_mock_light()
    _apply_reference_common(
        device.state,
        model="Original",
        color=HSBK(119.9981689453125, 1.0, 0.5, 3500),
        kelvin_min=2500,
        kelvin_max=9000,
    )
    return device


def create_reference_color_temperature_light() -> Light:
    """Create the normalized released-emulator tunable-white light."""
    device = create_mock_light()
    device.state.capabilities.has_color = False
    _apply_reference_common(
        device.state,
        model="LIFX White 900 (BR30)",
        color=HSBK(0.0, 0.0, 0.5, 3500),
        kelvin_min=2700,
        kelvin_max=6500,
    )
    return device


def create_reference_brightness_light() -> Light:
    """Create the normalized released-emulator brightness-only light."""
    device = create_mock_light()
    device.state.capabilities.has_color = False
    _apply_reference_common(
        device.state,
        model="LIFX Mini W",
        color=HSBK(0.0, 0.0, 0.5, 2700),
        kelvin_min=2700,
        kelvin_max=2700,
    )
    return device


def create_reference_infrared_light() -> InfraredLight:
    """Create the normalized released-emulator infrared light."""
    device = create_mock_infrared_light()
    _apply_reference_common(
        device.state,
        model="LIFX+ (A19)",
        color=HSBK(0.0, 1.0, 0.5, 3500),
        kelvin_min=2500,
        kelvin_max=9000,
    )
    device.state.infrared = 16384 / 65535
    return device


def create_reference_hev_light() -> HevLight:
    """Create the normalized released-emulator HEV light."""
    device = create_mock_hev_light()
    _apply_reference_common(
        device.state,
        model="LIFX Clean A19 1100lm",
        color=HSBK(180.0, 1.0, 0.5, 3500),
        kelvin_min=1500,
        kelvin_max=9000,
    )
    device.state.hev_cycle.remaining_s = 0
    device.state.hev_config.indication = True
    return device


def create_reference_multizone_light(*, extended: bool) -> MultiZoneLight:
    """Create a normalized released-emulator multizone light."""
    device = create_mock_multizone_light(extended=extended)
    zone_count = 80 if extended else 16
    zones = [
        HSBK(int(index * 65535 / zone_count) * 360 / 65535, 1.0, 0.5, 3500)
        for index in range(zone_count)
    ]
    device.state.zones = zones
    device.state.zone_count = zone_count
    _apply_reference_common(
        device.state,
        model="LIFX Beam" if extended else "LIFX Z",
        color=HSBK(
            177.7423095703125 if extended else 89.9945068359375,
            1.0,
            0.5,
            3500,
        ),
        kelvin_min=2500,
        kelvin_max=9000,
    )
    return device


def create_reference_legacy_multizone_light() -> MultiZoneLight:
    """Create the normalized released-emulator legacy multizone light."""
    return create_reference_multizone_light(extended=False)


def create_reference_extended_multizone_light() -> MultiZoneLight:
    """Create the normalized released-emulator extended multizone light."""
    return create_reference_multizone_light(extended=True)


def create_reference_matrix_light() -> MatrixLight:
    """Create the normalized released-emulator five-tile matrix light."""
    device = create_mock_matrix_light()
    chain = [
        _create_mock_tile(tile_index=index, user_x=float(index)) for index in range(5)
    ]
    tile_colors = [HSBK(0.0, 0.0, 0.5, 3500)] * 320
    device.state.chain = chain
    device.state.tile_orientations = dict.fromkeys(range(len(chain)), "Right Side Up")
    device.state.tile_colors = tile_colors
    device.state.tile_count = len(chain)
    _apply_reference_common(
        device.state,
        model="LIFX Tile",
        color=HSBK(0.0, 0.0, 0.5, 3500),
        kelvin_min=2500,
        kelvin_max=9000,
    )
    return device


def _create_reference_ceiling_light(
    *, model: str, product: int, width: int, zone_count: int
) -> CeilingLight:
    """Create a normalized released-emulator ceiling light."""
    device = create_mock_ceiling_light()
    color = HSBK(0.0, 0.0, 0.5, 3500)
    chain = [_create_mock_tile(product=product, width=width)]
    downlight_colors = [color] * zone_count
    device.state.chain = chain
    # tile_colors covers every zone of the tile: the downlight then the uplight
    device.state.tile_colors = [*downlight_colors, color]
    device.state.downlight_colors = downlight_colors
    device.state.tile_count = 1
    device.state.uplight_color = color
    device.state.uplight_is_on = True
    device.state.downlight_is_on = True
    device.state.uplight_zone = zone_count
    device.state.downlight_zones = slice(0, zone_count)
    device.state.capabilities.has_chain = False
    device.state.stored_uplight_color = color
    device.state.stored_downlight_colors = downlight_colors
    device.state.last_uplight_color = color
    device.state.last_downlight_colors = downlight_colors
    _apply_reference_common(
        device.state,
        model=model,
        color=color,
        kelvin_min=1500,
        kelvin_max=9000,
        firmware=(4, 10),
    )
    return device


def create_reference_ceiling_light() -> CeilingLight:
    """Create the normalized released-emulator 64-zone ceiling light."""
    return _create_reference_ceiling_light(
        model="LIFX Ceiling", product=176, width=8, zone_count=63
    )


def create_reference_ceiling_128_light() -> CeilingLight:
    """Create the normalized released-emulator 128-zone ceiling light."""
    return _create_reference_ceiling_light(
        model="LIFX Ceiling 13x26", product=201, width=16, zone_count=127
    )
