"""Tests for the Bosch SHC light platform."""

from unittest.mock import MagicMock, patch

from boschshcpy import SHCLight, SHCLightSwitch, SHCLightSwitchBSM, SHCMicromoduleDimmer
from boschshcpy.services_impl import PowerSwitchService

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.bosch_shc.light import SHCColorLight, SHCOnOffLight
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Device factory helpers
# ---------------------------------------------------------------------------


def _make_onoff_device(
    *,
    switchstate: PowerSwitchService.State = PowerSwitchService.State.ON,
    serial: str = "test-onoff-1",
    id: str = "hdm:ZigBee:onoff-1",
    root_device_id: str = "hdm:HomeMaticIP:root",
    manufacturer: str = "Bosch",
    device_model: str = "BSM",
    name: str = "Living Room Switch",
    status: str = "AVAILABLE",
    deleted: bool = False,
    spec=SHCLightSwitchBSM,
) -> MagicMock:
    """Create a mock on/off light switch device."""
    device = MagicMock(spec=spec)
    device.switchstate = switchstate
    device.serial = serial
    device.id = id
    device.root_device_id = root_device_id
    device.manufacturer = manufacturer
    device.device_model = device_model
    device.name = name
    device.status = status
    device.deleted = deleted
    device.device_services = []
    device.subscribe_callback = MagicMock()
    device.unsubscribe_callback = MagicMock()
    return device


def _make_color_device(
    *,
    binarystate: bool = True,
    brightness: int = 80,
    color: int = 4000,
    rgb: int = 0,
    min_color_temperature: int = 2700,
    max_color_temperature: int = 6500,
    supports_brightness: bool = True,
    supports_color_temp: bool = True,
    supports_color_hsb: bool = False,
    serial: str = "test-color-1",
    id: str = "hdm:ZigBee:color-1",
    root_device_id: str = "hdm:HomeMaticIP:root",
    manufacturer: str = "Bosch",
    device_model: str = "HUE_LIGHT",
    name: str = "Bedroom Light",
    status: str = "AVAILABLE",
    deleted: bool = False,
    spec=SHCLight,
) -> MagicMock:
    """Create a mock colour/dimmable light device."""
    device = MagicMock(spec=spec)
    device.binarystate = binarystate
    device.brightness = brightness
    device.color = color
    device.rgb = rgb
    device.min_color_temperature = min_color_temperature
    device.max_color_temperature = max_color_temperature
    device.supports_brightness = supports_brightness
    device.supports_color_temp = supports_color_temp
    device.supports_color_hsb = supports_color_hsb
    device.serial = serial
    device.id = id
    device.root_device_id = root_device_id
    device.manufacturer = manufacturer
    device.device_model = device_model
    device.name = name
    device.status = status
    device.deleted = deleted
    device.device_services = []
    device.subscribe_callback = MagicMock()
    device.unsubscribe_callback = MagicMock()
    return device


def _make_onoff_entity(device: MagicMock) -> SHCOnOffLight:
    """Create a SHCOnOffLight bypassing __init__ for unit tests."""
    entity = SHCOnOffLight.__new__(SHCOnOffLight)
    entity._device = device
    entity._entry_id = "test-entry-id"
    entity._attr_name = None
    entity._attr_unique_id = device.serial
    return entity


def _make_color_entity(device: MagicMock) -> SHCColorLight:
    """Create a SHCColorLight bypassing __init__ for unit tests."""
    entity = SHCColorLight.__new__(SHCColorLight)
    entity._device = device
    entity._entry_id = "test-entry-id"
    entity._attr_name = None
    entity._attr_unique_id = device.serial
    return entity


# ---------------------------------------------------------------------------
# SHCOnOffLight — basic state tests
# ---------------------------------------------------------------------------


def test_onoff_is_on_when_state_is_on() -> None:
    """is_on returns True when switchstate is ON."""
    device = _make_onoff_device(switchstate=PowerSwitchService.State.ON)
    entity = _make_onoff_entity(device)
    assert entity.is_on is True


def test_onoff_is_off_when_state_is_off() -> None:
    """is_on returns False when switchstate is OFF."""
    device = _make_onoff_device(switchstate=PowerSwitchService.State.OFF)
    entity = _make_onoff_entity(device)
    assert entity.is_on is False


def test_onoff_color_mode_is_onoff() -> None:
    """Color mode is ONOFF."""
    device = _make_onoff_device()
    entity = _make_onoff_entity(device)
    assert entity.color_mode == ColorMode.ONOFF


def test_onoff_supported_color_modes_onoff() -> None:
    """Supported color modes contains only ONOFF."""
    device = _make_onoff_device()
    entity = _make_onoff_entity(device)
    assert entity.supported_color_modes == {ColorMode.ONOFF}


def test_onoff_available_when_status_available() -> None:
    """Available returns True when device status is AVAILABLE."""
    device = _make_onoff_device(status="AVAILABLE")
    entity = _make_onoff_entity(device)
    assert entity.available is True


def test_onoff_unavailable_when_status_not_available() -> None:
    """Available returns False when device status is not AVAILABLE."""
    device = _make_onoff_device(status="UNAVAILABLE")
    entity = _make_onoff_entity(device)
    assert entity.available is False


# ---------------------------------------------------------------------------
# SHCOnOffLight — async service call tests
# ---------------------------------------------------------------------------


async def test_onoff_turn_on_calls_executor(hass: HomeAssistant) -> None:
    """turn_on calls async_add_executor_job with switchstate=True."""
    device = _make_onoff_device(switchstate=PowerSwitchService.State.OFF)
    entity = _make_onoff_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on()

    assert any(
        len(c[1]) == 3 and c[1][1] == "switchstate" and c[1][2] is True for c in calls
    ), f"switchstate=True not called; calls={calls}"


async def test_onoff_turn_off_calls_executor(hass: HomeAssistant) -> None:
    """turn_off calls async_add_executor_job with switchstate=False."""
    device = _make_onoff_device(switchstate=PowerSwitchService.State.ON)
    entity = _make_onoff_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_off()

    assert any(
        len(c[1]) == 3 and c[1][1] == "switchstate" and c[1][2] is False for c in calls
    ), f"switchstate=False not called; calls={calls}"


async def test_onoff_turn_on_with_micromodule_light_attached(
    hass: HomeAssistant,
) -> None:
    """turn_on works for micromodule_light_attached (SHCLightSwitch spec)."""
    device = _make_onoff_device(
        spec=SHCLightSwitch,
        switchstate=PowerSwitchService.State.OFF,
    )
    entity = _make_onoff_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on()

    assert any(c[1][1] == "switchstate" for c in calls)


# ---------------------------------------------------------------------------
# SHCColorLight — color mode/supported mode tests
# ---------------------------------------------------------------------------


def test_color_brightness_only_device() -> None:
    """Device with only brightness → ColorMode.BRIGHTNESS."""
    device = _make_color_device(
        supports_brightness=True,
        supports_color_temp=False,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    assert entity.color_mode == ColorMode.BRIGHTNESS
    assert ColorMode.BRIGHTNESS in entity.supported_color_modes
    assert ColorMode.COLOR_TEMP not in entity.supported_color_modes
    assert ColorMode.HS not in entity.supported_color_modes


def test_color_color_temp_device() -> None:
    """Device with color_temp (no HSB) → ColorMode.COLOR_TEMP."""
    device = _make_color_device(
        supports_brightness=True,
        supports_color_temp=True,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    assert entity.color_mode == ColorMode.COLOR_TEMP
    assert ColorMode.COLOR_TEMP in entity.supported_color_modes
    assert ColorMode.HS not in entity.supported_color_modes


def test_color_hsb_device_with_rgb_stored() -> None:
    """Device with HSB and non-zero RGB → active color_mode=HS."""
    device = _make_color_device(
        supports_color_hsb=True,
        rgb=0xFF8000,  # non-zero
    )
    entity = _make_color_entity(device)
    assert entity.color_mode == ColorMode.HS
    assert ColorMode.HS in entity.supported_color_modes
    assert ColorMode.COLOR_TEMP in entity.supported_color_modes


def test_color_hsb_device_without_rgb_stored() -> None:
    """Device with HSB and zero RGB → active color_mode=COLOR_TEMP."""
    device = _make_color_device(
        supports_color_hsb=True,
        rgb=0,
    )
    entity = _make_color_entity(device)
    assert entity.color_mode == ColorMode.COLOR_TEMP


def test_color_onoff_only_device() -> None:
    """Device with no capabilities → ColorMode.ONOFF."""
    device = _make_color_device(
        supports_brightness=False,
        supports_color_temp=False,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    assert entity.color_mode == ColorMode.ONOFF
    assert entity.supported_color_modes == {ColorMode.ONOFF}


# ---------------------------------------------------------------------------
# SHCColorLight — state property tests
# ---------------------------------------------------------------------------


def test_color_is_on_true() -> None:
    """is_on returns True when binarystate is True."""
    device = _make_color_device(binarystate=True)
    entity = _make_color_entity(device)
    assert entity.is_on is True


def test_color_is_on_false() -> None:
    """is_on returns False when binarystate is False."""
    device = _make_color_device(binarystate=False)
    entity = _make_color_entity(device)
    assert entity.is_on is False


def test_color_brightness_conversion() -> None:
    """Brightness converts from Bosch 0-100 → HA 0-255."""
    device = _make_color_device(brightness=80, supports_brightness=True)
    entity = _make_color_entity(device)
    # 80 * 255 / 100 = 204
    assert entity.brightness == 204


def test_color_brightness_zero() -> None:
    """Brightness of 0 maps to 0."""
    device = _make_color_device(brightness=0, supports_brightness=True)
    entity = _make_color_entity(device)
    assert entity.brightness == 0


def test_color_brightness_full() -> None:
    """Brightness of 100 maps to 255."""
    device = _make_color_device(brightness=100, supports_brightness=True)
    entity = _make_color_entity(device)
    assert entity.brightness == 255


def test_color_brightness_none_when_not_supported() -> None:
    """Brightness returns None when device does not support it."""
    device = _make_color_device(supports_brightness=False)
    entity = _make_color_entity(device)
    assert entity.brightness is None


def test_color_temp_kelvin() -> None:
    """color_temp_kelvin returns the device color value (Kelvin)."""
    device = _make_color_device(
        color=4000, supports_color_temp=True, supports_color_hsb=False
    )
    entity = _make_color_entity(device)
    assert entity.color_temp_kelvin == 4000


def test_color_temp_kelvin_none_when_zero() -> None:
    """color_temp_kelvin returns None when color is 0 (falsy)."""
    device = _make_color_device(
        color=0, supports_color_temp=True, supports_color_hsb=False
    )
    entity = _make_color_entity(device)
    assert entity.color_temp_kelvin is None


def test_color_temp_kelvin_none_when_unsupported() -> None:
    """color_temp_kelvin returns None when no color capability."""
    device = _make_color_device(supports_color_temp=False, supports_color_hsb=False)
    entity = _make_color_entity(device)
    assert entity.color_temp_kelvin is None


def test_color_min_color_temp_kelvin() -> None:
    """min_color_temp_kelvin returns device min value."""
    device = _make_color_device(min_color_temperature=2700)
    entity = _make_color_entity(device)
    assert entity.min_color_temp_kelvin == 2700


def test_color_max_color_temp_kelvin() -> None:
    """max_color_temp_kelvin returns device max value."""
    device = _make_color_device(max_color_temperature=6500)
    entity = _make_color_entity(device)
    assert entity.max_color_temp_kelvin == 6500


def test_color_min_color_temp_kelvin_fallback() -> None:
    """min_color_temp_kelvin falls back to 2700 when device returns 0."""
    device = _make_color_device(min_color_temperature=0)
    entity = _make_color_entity(device)
    assert entity.min_color_temp_kelvin == 2700


def test_color_max_color_temp_kelvin_fallback() -> None:
    """max_color_temp_kelvin falls back to 6500 when device returns 0."""
    device = _make_color_device(max_color_temperature=0)
    entity = _make_color_entity(device)
    assert entity.max_color_temp_kelvin == 6500


def test_color_hs_color_none_when_unsupported() -> None:
    """hs_color returns None when device does not support HSB."""
    device = _make_color_device(supports_color_hsb=False)
    entity = _make_color_entity(device)
    assert entity.hs_color is None


# ---------------------------------------------------------------------------
# SHCColorLight — HS color state tests
# ---------------------------------------------------------------------------


def test_color_hs_color_computed_from_rgb_int() -> None:
    """hs_color is correctly derived from the packed RGB integer."""
    # 0xFF8000 = R=255, G=128, B=0 → ~orange, H=30, S=100
    device = _make_color_device(
        supports_color_hsb=True,
        supports_color_temp=False,
        rgb=0xFF8000,
    )
    entity = _make_color_entity(device)
    hs = entity.hs_color
    assert hs is not None
    hue, saturation = hs
    # orange should have hue ~30 and saturation 100
    assert abs(hue - 30.0) < 1.0
    assert abs(saturation - 100.0) < 1.0


def test_color_hs_color_none_when_rgb_is_zero() -> None:
    """hs_color returns None when rgb value is 0 (unset)."""
    device = _make_color_device(supports_color_hsb=True, rgb=0)
    entity = _make_color_entity(device)
    assert entity.hs_color is None


# ---------------------------------------------------------------------------
# SHCColorLight — async service call tests
# ---------------------------------------------------------------------------


async def test_color_turn_on_when_off_sets_binarystate(hass: HomeAssistant) -> None:
    """turn_on sets binarystate=True when light is currently off."""
    device = _make_color_device(
        binarystate=False,
        brightness=50,
        color=4000,
        rgb=0,
        supports_brightness=True,
        supports_color_temp=True,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on()

    assert any(
        len(c[1]) == 3 and c[1][1] == "binarystate" and c[1][2] is True for c in calls
    ), f"binarystate=True not called; calls={calls}"


async def test_color_turn_on_with_brightness(hass: HomeAssistant) -> None:
    """turn_on with ATTR_BRIGHTNESS converts to Bosch 0-100 and calls executor."""
    device = _make_color_device(
        binarystate=True,
        brightness=50,
        color=4000,
        rgb=0,
        supports_brightness=True,
        supports_color_temp=True,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        # HA brightness 128 → Bosch ~50
        await entity.async_turn_on(brightness=128)

    brightness_calls = [c for c in calls if len(c[1]) == 3 and c[1][1] == "brightness"]
    assert len(brightness_calls) == 1
    bosch_brightness = brightness_calls[0][1][2]
    assert bosch_brightness == round(128 * 100 / 255)


async def test_color_turn_on_with_color_temp_kelvin(hass: HomeAssistant) -> None:
    """turn_on with ATTR_COLOR_TEMP_KELVIN sets device color."""
    device = _make_color_device(
        binarystate=True,
        brightness=50,
        color=4000,
        rgb=0,
        supports_brightness=True,
        supports_color_temp=True,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on(color_temp_kelvin=3000)

    assert any(
        len(c[1]) == 3 and c[1][1] == "color" and c[1][2] == 3000 for c in calls
    ), f"color=3000 not called; calls={calls}"


async def test_color_turn_on_brightness_not_set_when_unsupported(
    hass: HomeAssistant,
) -> None:
    """turn_on does not set brightness when device does not support it."""
    device = _make_color_device(
        binarystate=True,
        brightness=50,
        color=4000,
        rgb=0,
        supports_brightness=False,
        supports_color_temp=True,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on(brightness=200)

    assert not any(len(c[1]) == 3 and c[1][1] == "brightness" for c in calls), (
        "brightness setter called but should not have been"
    )


async def test_color_turn_off_sets_binarystate_false(hass: HomeAssistant) -> None:
    """turn_off calls binarystate=False via executor."""
    device = _make_color_device(
        binarystate=True,
        brightness=50,
        color=4000,
        rgb=0,
        supports_brightness=True,
        supports_color_temp=True,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_off()

    assert any(
        len(c[1]) == 3 and c[1][1] == "binarystate" and c[1][2] is False for c in calls
    ), f"binarystate=False not called; calls={calls}"


# ---------------------------------------------------------------------------
# SHCColorLight — HSB service call tests
# ---------------------------------------------------------------------------


async def test_color_turn_on_with_hs_color(hass: HomeAssistant) -> None:
    """turn_on with ATTR_HS_COLOR packs to RGB int and calls rgb setter."""
    device = _make_color_device(
        binarystate=True,
        supports_color_hsb=True,
        supports_color_temp=False,
        rgb=0,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))
        fn(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        # H=30, S=100 → pure orange (255,128,0)
        await entity.async_turn_on(hs_color=(30.0, 100.0))

    rgb_calls = [c for c in calls if len(c[1]) == 3 and c[1][1] == "rgb"]
    assert len(rgb_calls) == 1
    rgb_int = rgb_calls[0][1][2]
    # Decode and check approximate values
    red = (rgb_int >> 16) & 0xFF
    green = (rgb_int >> 8) & 0xFF
    blue = rgb_int & 0xFF
    assert red == 255
    assert green == 128
    assert blue == 0


async def test_color_hs_color_not_set_when_unsupported(hass: HomeAssistant) -> None:
    """turn_on does not call rgb setter when device does not support HSB."""
    device = _make_color_device(
        binarystate=True,
        supports_color_hsb=False,
        rgb=0,
    )
    entity = _make_color_entity(device)
    entity.hass = hass

    calls: list[tuple] = []

    async def mock_executor(fn, *args):
        calls.append((fn, args))

    with patch.object(hass, "async_add_executor_job", side_effect=mock_executor):
        await entity.async_turn_on(hs_color=(30.0, 100.0))

    assert not any(len(c[1]) == 3 and c[1][1] == "rgb" for c in calls), (
        "rgb setter called but device does not support HSB"
    )


# ---------------------------------------------------------------------------
# SHCMicromoduleDimmer tests
# ---------------------------------------------------------------------------


def test_dimmer_color_mode_brightness() -> None:
    """Dimmer without colour support → BRIGHTNESS mode."""
    device = _make_color_device(
        spec=SHCMicromoduleDimmer,
        binarystate=True,
        brightness=60,
        supports_brightness=True,
        supports_color_temp=False,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    assert entity.color_mode == ColorMode.BRIGHTNESS


def test_dimmer_brightness_conversion() -> None:
    """Dimmer brightness converts 60 → round(60*255/100) = 153."""
    device = _make_color_device(
        spec=SHCMicromoduleDimmer,
        binarystate=True,
        brightness=60,
        supports_brightness=True,
        supports_color_temp=False,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    assert entity.brightness == 153


def test_dimmer_is_on() -> None:
    """is_on reflects binarystate."""
    device = _make_color_device(
        spec=SHCMicromoduleDimmer,
        binarystate=True,
        brightness=60,
        supports_brightness=True,
        supports_color_temp=False,
        supports_color_hsb=False,
    )
    entity = _make_color_entity(device)
    assert entity.is_on is True


# ---------------------------------------------------------------------------
# async_setup_entry tests (use hass.config_entries.async_setup per W7420)
# ---------------------------------------------------------------------------


def _make_mock_session(
    *,
    unique_id: str = "test-shc-id",
    light_switches_bsm: list | None = None,
    micromodule_light_attached: list | None = None,
    hue_lights: list | None = None,
    ledvance_lights: list | None = None,
    micromodule_dimmers: list | None = None,
) -> MagicMock:
    """Build a minimal mock SHCSession for async_setup_entry tests."""
    mock_session = MagicMock()
    mock_session.information.unique_id = unique_id
    mock_session.information.updateState.name = "NO_UPDATE_AVAILABLE"
    mock_session.information.version = "1.0"
    mock_session.device_helper.light_switches_bsm = (
        light_switches_bsm if light_switches_bsm is not None else []
    )
    mock_session.device_helper.micromodule_light_attached = (
        micromodule_light_attached if micromodule_light_attached is not None else []
    )
    mock_session.device_helper.hue_lights = hue_lights if hue_lights is not None else []
    mock_session.device_helper.ledvance_lights = (
        ledvance_lights if ledvance_lights is not None else []
    )
    mock_session.device_helper.micromodule_dimmers = (
        micromodule_dimmers if micromodule_dimmers is not None else []
    )
    return mock_session


def _make_config_entry(unique_id: str = "test-shc-id") -> MockConfigEntry:
    """Build a MockConfigEntry for the bosch_shc domain."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={
            "host": "1.2.3.4",
            "ssl_certificate": "/fake/cert.pem",
            "ssl_key": "/fake/key.pem",
            "token": "test-token",
            "hostname": "shc012345",
        },
        title="Test SHC",
    )


async def test_async_setup_entry_light_switches_bsm(hass: HomeAssistant) -> None:
    """async_setup_entry creates SHCOnOffLight from light_switches_bsm."""
    mock_device = _make_onoff_device(spec=SHCLightSwitchBSM)
    mock_session = _make_mock_session(light_switches_bsm=[mock_device])

    entry = _make_config_entry("test-shc-bsm")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_micromodule_light_attached(
    hass: HomeAssistant,
) -> None:
    """async_setup_entry creates SHCOnOffLight from micromodule_light_attached."""
    mock_device = _make_onoff_device(spec=SHCLightSwitch)
    mock_session = _make_mock_session(micromodule_light_attached=[mock_device])

    entry = _make_config_entry("test-shc-mla")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_hue_lights(hass: HomeAssistant) -> None:
    """async_setup_entry creates SHCColorLight from hue_lights."""
    mock_device = _make_color_device(spec=SHCLight)
    mock_session = _make_mock_session(hue_lights=[mock_device])

    entry = _make_config_entry("test-shc-hue")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_ledvance_lights(hass: HomeAssistant) -> None:
    """async_setup_entry creates SHCColorLight from ledvance_lights."""
    mock_device = _make_color_device(spec=SHCLight)
    mock_session = _make_mock_session(ledvance_lights=[mock_device])

    entry = _make_config_entry("test-shc-lv")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_micromodule_dimmers(hass: HomeAssistant) -> None:
    """async_setup_entry creates SHCColorLight from micromodule_dimmers."""
    mock_device = _make_color_device(spec=SHCMicromoduleDimmer)
    mock_session = _make_mock_session(micromodule_dimmers=[mock_device])

    entry = _make_config_entry("test-shc-dim")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_empty(hass: HomeAssistant) -> None:
    """async_setup_entry handles empty device lists without error."""
    mock_session = _make_mock_session()

    entry = _make_config_entry("test-shc-empty")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"


async def test_async_setup_entry_multiple_collections(hass: HomeAssistant) -> None:
    """async_setup_entry aggregates entities from all collections."""
    mock_session = _make_mock_session(
        unique_id="test-shc-multi",
        light_switches_bsm=[_make_onoff_device(serial="bsm-1", id="id-bsm-1")],
        micromodule_light_attached=[
            _make_onoff_device(spec=SHCLightSwitch, serial="mm-1", id="id-mm-1")
        ],
        hue_lights=[_make_color_device(serial="hue-1", id="id-hue-1")],
        ledvance_lights=[_make_color_device(serial="lv-1", id="id-lv-1")],
        micromodule_dimmers=[
            _make_color_device(spec=SHCMicromoduleDimmer, serial="dim-1", id="id-dim-1")
        ],
    )

    entry = _make_config_entry("test-shc-multi")
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.bosch_shc.async_get_instance",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state.value == "loaded"
