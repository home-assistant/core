"""Test helpers for the lifx integration."""

import inspect
from typing import TypeVar
from unittest.mock import AsyncMock

from lifx import (
    HSBK,
    CeilingLight,
    CeilingLightState,
    CollectionInfo,
    Connectivity,
    Device,
    DeviceVersion,
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
    MirrorLight,
    MirrorLightState,
    MultiZoneLight,
    MultiZoneLightState,
    ThreadInfo,
    ThreadRoutingRole,
    TileInfo,
    WifiInfo,
    mac_candidates_for_serial,
)
from lifx.products import get_mirror_layout, get_product
from lifx.protocol.models import (
    MAC_OFFSET_FIRMWARE_MAJOR,
    MAC_OFFSET_FIRMWARE_MIN_MINOR,
)

from homeassistant.components.lifx.light import LIFX_MIN_COLOR_RAMP

IP_ADDRESS = "127.0.0.1"
SERIAL = "d073d5ddeecc"
# The colon separated serial written by releases that treated it as a MAC
LEGACY_SERIAL = "d0:73:d5:dd:ee:cc"
MAC_ADDRESS = "d0:73:d5:dd:ee:cc"
LABEL = "My Bulb"
GROUP = "My Group"
INFRARED_SELECT_ENTITY_ID = "select.my_group_my_bulb_infrared_brightness"
POWER_ON = 65535

# Product ids, zone counts, tile sizes and firmware follow the lifx-emulator
# product specs (lifx_emulator/products/specs.yml) unless noted otherwise
COLOR_PRODUCT = 163
COLOR_TEMPERATURE_PRODUCT = 18
BRIGHTNESS_PRODUCT = 51
INFRARED_PRODUCT = 29
HEV_PRODUCT = 90
LEGACY_MULTIZONE_PRODUCT = 31
LEGACY_MULTIZONE_ZONES = 16
EXTENDED_MULTIZONE_PRODUCT = 38
EXTENDED_MULTIZONE_ZONES = 80
TILE_PRODUCT = 55
TILE_COUNT = 5
LUNA_PRODUCT = 219
LUNA_WIDTH = 7
LUNA_HEIGHT = 5
CEILING_PRODUCT = 176
CEILING_WIDTH = 8
CEILING_HEIGHT = 8
MIRROR_PRODUCT = 267
MIRROR_ZONES = 25

# The emulator's default for a product without one in the specs
DEFAULT_FIRMWARE = (3, 70)
LEGACY_MULTIZONE_FIRMWARE = (2, 60)
TILE_FIRMWARE = (3, 50)
CEILING_FIRMWARE = (4, 10)
# The release that widens the Luna and Mirror kelvin range
LUNA_FIRMWARE = (4, 148)
MIRROR_FIRMWARE = (4, 148)
# Thread needs fourth generation hardware, and firmware 4.200 or later
THREAD_FIRMWARE = (4, 200)

type MockDevice = (
    Light
    | MultiZoneLight
    | MatrixLight
    | CeilingLight
    | MirrorLight
    | HevLight
    | InfraredLight
)
type MockState = (
    LightState
    | MultiZoneLightState
    | MatrixLightState
    | CeilingLightState
    | MirrorLightState
    | HevLightState
    | InfraredLightState
)

_DeviceT = TypeVar("_DeviceT", bound=MockDevice)


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


def set_connectivity(device: MockDevice, connectivity: Connectivity) -> None:
    """Report the radio as discovery metadata would."""
    device._set_connectivity(connectivity)


def _mac_address(serial: str, firmware: FirmwareInfo) -> str:
    """Return the MAC the library derives from the serial and firmware."""
    direct_mac, offset_mac = mac_candidates_for_serial(serial)
    if (
        firmware.version_major == MAC_OFFSET_FIRMWARE_MAJOR
        and firmware.version_minor >= MAC_OFFSET_FIRMWARE_MIN_MINOR
    ):
        return offset_mac
    return direct_mac


def _create_device(
    device_type: type[_DeviceT],
    product: int,
    firmware: tuple[int, int],
    *,
    color: HSBK,
    ip: str = IP_ADDRESS,
    serial: str = SERIAL,
) -> tuple[_DeviceT, LightState]:
    """Create a library device for a product and the light state it would fetch."""
    device = device_type(serial=serial, ip=ip)
    host_firmware = FirmwareInfo(
        build=0, version_major=firmware[0], version_minor=firmware[1]
    )
    version = DeviceVersion(vendor=1, product=product)
    device._version = version
    device._host_firmware = host_firmware
    device._process_capabilities(version, host_firmware)
    assert device._capabilities is not None
    light_state = LightState(
        model=device._capabilities.name,
        label=LABEL,
        serial=device.serial,
        mac_address=_mac_address(device.serial, host_firmware),
        capabilities=device._create_capabilities(),
        power=POWER_ON,
        host_firmware=host_firmware,
        # The emulator reports the host firmware for the WiFi module too
        wifi_firmware=host_firmware,
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
        color=color,
        last_updated=0.0,
    )
    return device, light_state


def _mock_requests(device: Device) -> None:
    """Stop every public request reaching the network."""
    for name, _ in inspect.getmembers(type(device), inspect.iscoroutinefunction):
        if not name.startswith("_"):
            setattr(device, name, AsyncMock())


def _attach_state(device: _DeviceT, state: MockState) -> _DeviceT:
    """Give the device the state it would have fetched."""
    state.last_updated = 0.0
    device._state = state
    _mock_requests(device)
    device.get_color = AsyncMock(return_value=(state.color, state.power, state.label))
    return device


def create_mock_device_without_state() -> Device:
    """Create a device found by address whose state has not been read."""
    device = Device(serial=SERIAL, ip=IP_ADDRESS)
    _mock_requests(device)
    return device


def _create_tile(
    *,
    product: int,
    firmware: FirmwareInfo,
    width: int,
    height: int,
    tile_index: int = 0,
) -> TileInfo:
    """Create the metadata a tile on the device chain reports."""
    return TileInfo(
        tile_index=tile_index,
        accel_meas_x=0,
        accel_meas_y=0,
        accel_meas_z=0,
        user_x=float(tile_index),
        user_y=0.0,
        width=width,
        height=height,
        supported_frame_buffers=0,
        device_version_vendor=1,
        device_version_product=product,
        device_version_version=0,
        firmware_build=0,
        firmware_version_minor=firmware.version_minor,
        firmware_version_major=firmware.version_major,
    )


def _create_matrix_state(
    light_state: LightState, product: int, chain_length: int, width: int, height: int
) -> MatrixLightState:
    """Create the matrix state of a chain of identical tiles."""
    chain = [
        _create_tile(
            product=product,
            firmware=light_state.host_firmware,
            width=width,
            height=height,
            tile_index=index,
        )
        for index in range(chain_length)
    ]
    return MatrixLightState.from_light_state(
        light_state,
        chain=chain,
        tile_orientations={
            index: tile.nearest_orientation for index, tile in enumerate(chain)
        },
        tile_colors=[light_state.color] * (chain_length * width * height),
        effect=FirmwareEffect.OFF,
    )


def create_mock_light(
    *,
    ip: str = IP_ADDRESS,
    serial: str = SERIAL,
) -> Light:
    """Create a fourth generation color bulb."""
    device, state = _create_device(
        Light,
        COLOR_PRODUCT,
        THREAD_FIRMWARE,
        color=HSBK(119.9981689453125, 1.0, 0.5, 3500),
        ip=ip,
        serial=serial,
    )
    return _attach_state(device, state)


def create_mock_thread_light() -> Light:
    """Create a fourth generation color bulb connected over Thread."""
    device = create_mock_light()
    set_connectivity(device, Connectivity.THREAD)
    device.state.thread_info = ThreadInfo(
        rloc=1024,
        network_name="Private mesh",
        role=ThreadRoutingRole.ROUTER,
        next_hop=2048,
        link_quality_in=3,
        link_quality_out=3,
        link_margin_db=40,
    )
    return device


def create_mock_color_temperature_light() -> Light:
    """Create a tunable white bulb."""
    device, state = _create_device(
        Light,
        COLOR_TEMPERATURE_PRODUCT,
        DEFAULT_FIRMWARE,
        color=HSBK(0.0, 0.0, 0.5, 3500),
    )
    return _attach_state(device, state)


def create_mock_brightness_light() -> Light:
    """Create a fixed white, brightness only bulb."""
    device, state = _create_device(
        Light,
        BRIGHTNESS_PRODUCT,
        DEFAULT_FIRMWARE,
        color=HSBK(0.0, 0.0, 0.5, 2700),
    )
    return _attach_state(device, state)


def create_mock_infrared_light() -> InfraredLight:
    """Create a night vision bulb."""
    device, light_state = _create_device(
        InfraredLight,
        INFRARED_PRODUCT,
        DEFAULT_FIRMWARE,
        color=HSBK(0.0, 1.0, 0.5, 3500),
    )
    state = InfraredLightState.from_light_state(light_state, infrared=16384 / 65535)
    return _attach_state(device, state)


def create_mock_hev_light() -> HevLight:
    """Create a LIFX Clean bulb."""
    device, light_state = _create_device(
        HevLight,
        HEV_PRODUCT,
        DEFAULT_FIRMWARE,
        color=HSBK(180.0, 1.0, 0.5, 3500),
    )
    state = HevLightState.from_light_state(
        light_state,
        hev_cycle=HevCycleState(duration_s=7200, remaining_s=0, last_power=False),
        hev_config=HevConfig(indication=True, duration_s=7200),
        hev_result=LightLastHevCycleResult.SUCCESS,
    )
    return _attach_state(device, state)


def create_mock_multizone_light(*, extended: bool = True) -> MultiZoneLight:
    """Create a Beam, or a LIFX Z on firmware without extended multizone."""
    if extended:
        product = EXTENDED_MULTIZONE_PRODUCT
        zone_count = EXTENDED_MULTIZONE_ZONES
        firmware = DEFAULT_FIRMWARE
        color = HSBK(177.7423095703125, 1.0, 0.5, 3500)
    else:
        product = LEGACY_MULTIZONE_PRODUCT
        zone_count = LEGACY_MULTIZONE_ZONES
        firmware = LEGACY_MULTIZONE_FIRMWARE
        color = HSBK(89.9945068359375, 1.0, 0.5, 3500)
    device, light_state = _create_device(MultiZoneLight, product, firmware, color=color)
    # A rainbow, as the library decodes the hues the emulator reports
    zones = [
        HSBK(int(index * 65535 / zone_count) * 360 / 0x10000, 1.0, 0.5, 3500)
        for index in range(zone_count)
    ]
    state = MultiZoneLightState.from_light_state(
        light_state, zones=zones, effect=FirmwareEffect.OFF
    )
    return _attach_state(device, state)


def create_mock_matrix_light() -> MatrixLight:
    """Create a chain of LIFX Tiles on their final firmware."""
    device, light_state = _create_device(
        MatrixLight, TILE_PRODUCT, TILE_FIRMWARE, color=HSBK(0.0, 0.0, 0.5, 3500)
    )
    state = _create_matrix_state(light_state, TILE_PRODUCT, TILE_COUNT, 8, 8)
    return _attach_state(device, state)


def create_mock_luna_light() -> MatrixLight:
    """Create a LIFX Luna, a single tile that is not square."""
    device, light_state = _create_device(
        MatrixLight, LUNA_PRODUCT, LUNA_FIRMWARE, color=HSBK(0.0, 0.0, 0.5, 3500)
    )
    state = _create_matrix_state(light_state, LUNA_PRODUCT, 1, LUNA_WIDTH, LUNA_HEIGHT)
    return _attach_state(device, state)


def create_mock_ceiling_light() -> CeilingLight:
    """Create a 64 zone LIFX Ceiling with both components on."""
    product = get_product(CEILING_PRODUCT)
    assert product is not None
    assert product.uplight_coords is not None
    x, y = product.uplight_coords
    uplight_zone = x + y * CEILING_WIDTH
    downlight_zones = slice(0, uplight_zone)
    device, light_state = _create_device(
        CeilingLight, CEILING_PRODUCT, CEILING_FIRMWARE, color=HSBK(0.0, 0.0, 0.5, 3500)
    )
    matrix_state = _create_matrix_state(
        light_state, CEILING_PRODUCT, 1, CEILING_WIDTH, CEILING_HEIGHT
    )
    tile_colors = matrix_state.tile_colors
    state = CeilingLightState.from_matrix_state(
        matrix_state,
        uplight_color=tile_colors[uplight_zone],
        downlight_colors=tile_colors[downlight_zones],
        uplight_zone=uplight_zone,
        downlight_zones=downlight_zones,
    )
    return _attach_state(device, state)


def create_mock_mirror_light() -> MirrorLight:
    """Create a LIFX Mirror with both components on."""
    # The 50 zones are spread across a 4x13 buffer, so the tile has 52 colors
    layout = get_mirror_layout(MIRROR_PRODUCT)
    assert layout is not None
    device, light_state = _create_device(
        MirrorLight, MIRROR_PRODUCT, MIRROR_FIRMWARE, color=HSBK(0.0, 0.0, 0.5, 3500)
    )
    matrix_state = _create_matrix_state(
        light_state, MIRROR_PRODUCT, 1, layout.width, layout.height
    )
    tile_colors = matrix_state.tile_colors
    state = MirrorLightState.from_matrix_state(
        matrix_state,
        front_colors=[tile_colors[position] for position in layout.front_positions],
        back_colors=[tile_colors[position] for position in layout.back_positions],
        front_positions=layout.front_positions,
        back_positions=layout.back_positions,
    )
    return _attach_state(device, state)
