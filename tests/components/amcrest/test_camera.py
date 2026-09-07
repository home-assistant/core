"""Tests for the Amcrest camera platform."""

from types import SimpleNamespace

from amcrest import AmcrestError
import pytest

from homeassistant.components.amcrest.const import CBW, DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN, async_get_image
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import _MockAmcrestAPI, setup_amcrest

_CAMERA = "camera.amcrest_camera"


class _CameraAPI(_MockAmcrestAPI):
    """Adds the setter surface the camera services drive.

    Kept here rather than in conftest so the shared fixtures stay identical to
    the ones in the unique_id PR. Setters mutate the same state the getters
    read, because _async_change_setting writes a value then reads it back and
    retries if the two disagree.
    """

    def __init__(self) -> None:
        """Record calls that have no readable state to assert against."""
        super().__init__()
        self.indicator_light = False
        self.snapshot_bytes = b"jpeg-bytes"
        self.mjpeg_url = "http://192.168.1.100/mjpeg"
        self.preset_calls: list[int] = []
        self.tour_calls: list[bool] = []
        self.ptz_calls: list[tuple[str, str]] = []

    async def async_set_video_enabled(
        self, enable: bool, *, channel: int = 0, stream: int = 0
    ) -> None:
        self.video_enabled = enable

    async def async_set_audio_enabled(
        self, enable: bool, *, channel: int = 0, stream: int = 0
    ) -> None:
        self.audio_enabled = enable

    async def async_set_record_mode(self, mode: int) -> None:
        self.record_mode = "Manual" if mode == 1 else "Automatic"

    async def async_set_motion_detection(self, enable: bool) -> None:
        self.motion_detector = enable

    async def async_set_motion_recording(self, enable: bool) -> None:
        self.motion_recording = enable

    async def async_set_day_night_color(self, value: int, *, channel: int = 0) -> None:
        self.day_night_color = value

    async def async_go_to_preset(self, *, preset_point_number: int) -> None:
        if "go_to_preset" in self._raise_on:
            raise self._raise_on["go_to_preset"]
        self.preset_calls.append(preset_point_number)

    async def async_tour(self, *, start: bool) -> None:
        if "tour" in self._raise_on:
            raise self._raise_on["tour"]
        self.tour_calls.append(start)

    async def async_ptz_control_command(
        self, *, action: str, code: str, arg1: int, arg2: int, arg3: int
    ) -> None:
        if "ptz_control_command" in self._raise_on:
            raise self._raise_on["ptz_control_command"]
        self.ptz_calls.append((action, code))

    async def async_command(self, cmd: str) -> SimpleNamespace:
        # Only the indicator light is driven through the raw command endpoint.
        if "setConfig" in cmd:
            self.indicator_light = "true" in cmd
            return SimpleNamespace(content=b"OK")
        value = "true" if self.indicator_light else "false"
        return SimpleNamespace(content=f"table.LightGlobal[0].Enable={value}".encode())

    async def async_snapshot(self, timeout: tuple[float, float] | None = None) -> bytes:
        if "snapshot" in self._raise_on:
            raise self._raise_on["snapshot"]
        return self.snapshot_bytes


@pytest.fixture
def camera_api() -> _CameraAPI:
    """Return a mock API with the camera setter surface."""
    return _CameraAPI()


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    """Call one of the amcrest camera services against the test camera."""
    await hass.services.async_call(
        DOMAIN, service, {"entity_id": _CAMERA, **data}, blocking=True
    )


@pytest.mark.usefixtures("mock_event_monitor")
async def test_camera_exposes_device_attributes(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """The camera publishes brand, model and stream state after setup."""
    await setup_amcrest(hass, camera_api)

    state = hass.states.get(_CAMERA)
    assert state.state == "streaming"
    assert state.attributes["brand"] == "Amcrest"
    assert state.attributes["model_name"] == "IP2M-841"
    assert state.attributes["audio"] == "off"
    assert state.attributes["motion_recording"] == "off"
    assert state.attributes["color_bw"] == "color"


@pytest.mark.usefixtures("mock_event_monitor")
async def test_camera_unavailable_when_offline(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """An unreachable camera reports unavailable and publishes no device details."""
    camera_api.available = False

    await setup_amcrest(hass, camera_api)

    state = hass.states.get(_CAMERA)
    assert state.state == STATE_UNAVAILABLE
    # Absent rather than stale: no API contact was made.
    assert "brand" not in state.attributes


@pytest.mark.usefixtures("mock_event_monitor")
async def test_camera_update_error_is_handled(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """An AmcrestError while reading device details does not propagate."""
    camera_api.set_error("vendor_information", AmcrestError("timeout"))

    await setup_amcrest(hass, camera_api)

    assert hass.states.get(_CAMERA) is not None


@pytest.mark.parametrize(
    "vendor",
    [pytest.param("", id="empty_string"), pytest.param(None, id="none")],
)
@pytest.mark.usefixtures("mock_event_monitor")
async def test_camera_unknown_brand_fallback(
    hass: HomeAssistant, camera_api: _CameraAPI, vendor: str | None
) -> None:
    """A camera that reports no vendor falls back to a placeholder brand."""
    camera_api.vendor = vendor

    await setup_amcrest(hass, camera_api)

    assert hass.states.get(_CAMERA).attributes["brand"] == "unknown"


@pytest.mark.parametrize(
    ("service", "attribute", "expected"),
    [
        pytest.param("enable_audio", "audio", "on", id="enable_audio"),
        pytest.param("disable_audio", "audio", "off", id="disable_audio"),
        pytest.param(
            "enable_motion_recording", "motion_recording", "on", id="enable_motion_rec"
        ),
        pytest.param(
            "disable_motion_recording",
            "motion_recording",
            "off",
            id="disable_motion_rec",
        ),
    ],
)
@pytest.mark.usefixtures("mock_event_monitor")
async def test_toggle_services_update_attributes(
    hass: HomeAssistant,
    camera_api: _CameraAPI,
    service: str,
    attribute: str,
    expected: str,
) -> None:
    """The enable/disable services write to the camera and refresh the attribute."""
    await setup_amcrest(hass, camera_api)

    await _call(hass, service)
    await hass.async_block_till_done()

    assert hass.states.get(_CAMERA).attributes[attribute] == expected


@pytest.mark.usefixtures("mock_event_monitor")
async def test_recording_services_change_state(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """Enabling recording flips the camera state and the underlying record mode."""
    await setup_amcrest(hass, camera_api)

    await _call(hass, "enable_recording")
    await hass.async_block_till_done()
    assert camera_api.record_mode == "Manual"
    assert hass.states.get(_CAMERA).state == "recording"

    await _call(hass, "disable_recording")
    await hass.async_block_till_done()
    assert camera_api.record_mode == "Automatic"
    assert hass.states.get(_CAMERA).state == "streaming"


@pytest.mark.usefixtures("mock_event_monitor")
async def test_set_color_bw_service(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """The color_bw service writes the selected mode and reflects it back."""
    await setup_amcrest(hass, camera_api)

    await _call(hass, "set_color_bw", color_bw="bw")
    await hass.async_block_till_done()

    assert camera_api.day_night_color == CBW.index("bw")
    assert hass.states.get(_CAMERA).attributes["color_bw"] == "bw"


@pytest.mark.usefixtures("mock_event_monitor")
async def test_goto_preset_service(hass: HomeAssistant, camera_api: _CameraAPI) -> None:
    """The goto_preset service forwards the preset number to the camera."""
    await setup_amcrest(hass, camera_api)

    await _call(hass, "goto_preset", preset=3)
    await hass.async_block_till_done()

    assert camera_api.preset_calls == [3]


@pytest.mark.usefixtures("mock_event_monitor")
async def test_tour_services(hass: HomeAssistant, camera_api: _CameraAPI) -> None:
    """The tour services start and stop a camera tour."""
    await setup_amcrest(hass, camera_api)

    await _call(hass, "start_tour")
    await _call(hass, "stop_tour")
    await hass.async_block_till_done()

    assert camera_api.tour_calls == [True, False]


@pytest.mark.usefixtures("mock_event_monitor")
async def test_ptz_control_service(hass: HomeAssistant, camera_api: _CameraAPI) -> None:
    """PTZ control issues a matched start/stop pair for the requested movement."""
    await setup_amcrest(hass, camera_api)

    await _call(hass, "ptz_control", movement="zoom_in", travel_time=0.0)
    await hass.async_block_till_done()

    assert [action for action, _ in camera_api.ptz_calls] == ["start", "stop"]
    codes = {code for _, code in camera_api.ptz_calls}
    assert len(codes) == 1


@pytest.mark.parametrize(
    ("service", "error_key", "data"),
    [
        pytest.param("goto_preset", "go_to_preset", {"preset": 1}, id="goto_preset"),
        pytest.param("start_tour", "tour", {}, id="start_tour"),
        pytest.param(
            "ptz_control",
            "ptz_control_command",
            {"movement": "left", "travel_time": 0.0},
            id="ptz_control",
        ),
    ],
)
@pytest.mark.usefixtures("mock_event_monitor")
async def test_service_errors_are_logged_not_raised(
    hass: HomeAssistant,
    camera_api: _CameraAPI,
    service: str,
    error_key: str,
    data: dict[str, object],
) -> None:
    """A camera that fails mid-service logs the error rather than raising."""
    await setup_amcrest(hass, camera_api)
    camera_api.set_error(error_key, AmcrestError("timeout"))

    await _call(hass, service, **data)
    await hass.async_block_till_done()

    assert hass.states.get(_CAMERA) is not None


@pytest.mark.usefixtures("mock_event_monitor")
async def test_camera_image_returns_snapshot(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """A still image request returns the camera's snapshot bytes."""
    await setup_amcrest(hass, camera_api)

    image = await async_get_image(hass, _CAMERA)

    assert image.content == b"jpeg-bytes"


@pytest.mark.usefixtures("mock_event_monitor")
async def test_turn_off_stops_streaming(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """Turning the camera off disables the video stream."""
    await setup_amcrest(hass, camera_api)
    assert hass.states.get(_CAMERA).state == "streaming"

    await hass.services.async_call(
        CAMERA_DOMAIN, "turn_off", {"entity_id": _CAMERA}, blocking=True
    )
    await hass.async_block_till_done()

    assert camera_api.video_enabled is False


@pytest.mark.usefixtures("mock_event_monitor")
async def test_snapshot_refused_when_camera_offline(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """A snapshot is refused rather than attempted while the camera is unreachable."""
    camera_api.available = False
    await setup_amcrest(hass, camera_api)

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, _CAMERA)


@pytest.mark.usefixtures("mock_event_monitor")
async def test_snapshot_error_is_handled(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """An AmcrestError while snapshotting surfaces as no image, not a traceback."""
    await setup_amcrest(hass, camera_api)
    camera_api.set_error("snapshot", AmcrestError("timeout"))

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, _CAMERA)


@pytest.mark.usefixtures("mock_event_monitor")
async def test_setting_that_never_takes_is_abandoned(
    hass: HomeAssistant, camera_api: _CameraAPI
) -> None:
    """A write the camera silently ignores is retried, then given up on."""

    # Accept the write but never actually change: _async_change_setting reads the
    # value back, sees the mismatch, and retries before logging and moving on.
    async def _ignore(enable: bool, *, channel: int = 0, stream: int = 0) -> None:
        return

    await setup_amcrest(hass, camera_api)
    camera_api.async_set_audio_enabled = _ignore

    await _call(hass, "enable_audio")
    await hass.async_block_till_done()

    assert camera_api.audio_enabled is False
    assert hass.states.get(_CAMERA).attributes["audio"] == "off"
