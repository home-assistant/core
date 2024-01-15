"""The tests for Home Assistant ffmpeg."""
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

from homeassistant.components import ffmpeg
from homeassistant.components.ffmpeg import (
    DOMAIN,
    SERVICE_RESTART,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component, setup_component

from tests.common import assert_setup_component, get_test_home_assistant


@callback
def async_start(hass, entity_id=None):
    """Start a FFmpeg process on entity.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_START, data))


@callback
def async_stop(hass, entity_id=None):
    """Stop a FFmpeg process on entity.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_STOP, data))


@callback
def async_restart(hass, entity_id=None):
    """Restart a FFmpeg process on entity.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_RESTART, data))


class MockFFmpegDev(ffmpeg.FFmpegBase):
    """FFmpeg device mock."""

    def __init__(self, hass, initial_state=True, entity_id="test.ffmpeg_device"):
        """Initialize mock."""
        super().__init__(None, initial_state)

        self.hass = hass
        self.entity_id = entity_id
        self.ffmpeg = MagicMock()
        self.called_stop = False
        self.called_start = False
        self.called_restart = False
        self.called_entities = None

    async def _async_start_ffmpeg(self, entity_ids):
        """Mock start."""
        self.called_start = True
        self.called_entities = entity_ids

    async def _async_stop_ffmpeg(self, entity_ids):
        """Mock stop."""
        self.called_stop = True
        self.called_entities = entity_ids


class TestFFmpegSetup:
    """Test class for ffmpeg."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Set up ffmpeg component."""
        with assert_setup_component(1):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        assert self.hass.data[ffmpeg.DATA_FFMPEG].binary == "ffmpeg"

    def test_setup_component_test_service(self):
        """Set up ffmpeg component test services."""
        with assert_setup_component(1):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        assert self.hass.services.has_service(ffmpeg.DOMAIN, "start")
        assert self.hass.services.has_service(ffmpeg.DOMAIN, "stop")
        assert self.hass.services.has_service(ffmpeg.DOMAIN, "restart")


async def test_setup_component_test_register(hass: HomeAssistant) -> None:
    """Set up ffmpeg component test register."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass)
    ffmpeg_dev._async_stop_ffmpeg = AsyncMock()
    ffmpeg_dev._async_start_ffmpeg = AsyncMock()
    await ffmpeg_dev.async_added_to_hass()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(ffmpeg_dev._async_start_ffmpeg.mock_calls) == 2

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(ffmpeg_dev._async_stop_ffmpeg.mock_calls) == 2


async def test_setup_component_test_register_no_startup(hass: HomeAssistant) -> None:
    """Set up ffmpeg component test register without startup."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    ffmpeg_dev._async_stop_ffmpeg = AsyncMock()
    ffmpeg_dev._async_start_ffmpeg = AsyncMock()
    await ffmpeg_dev.async_added_to_hass()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(ffmpeg_dev._async_start_ffmpeg.mock_calls) == 1

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(ffmpeg_dev._async_stop_ffmpeg.mock_calls) == 2


async def test_setup_component_test_service_start(hass: HomeAssistant) -> None:
    """Set up ffmpeg component test service start."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    await ffmpeg_dev.async_added_to_hass()

    async_start(hass)
    await hass.async_block_till_done()

    assert ffmpeg_dev.called_start


async def test_setup_component_test_service_stop(hass: HomeAssistant) -> None:
    """Set up ffmpeg component test service stop."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    await ffmpeg_dev.async_added_to_hass()

    async_stop(hass)
    await hass.async_block_till_done()

    assert ffmpeg_dev.called_stop


async def test_setup_component_test_service_restart(hass: HomeAssistant) -> None:
    """Set up ffmpeg component test service restart."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    await ffmpeg_dev.async_added_to_hass()

    async_restart(hass)
    await hass.async_block_till_done()

    assert ffmpeg_dev.called_stop
    assert ffmpeg_dev.called_start


async def test_setup_component_test_service_start_with_entity(
    hass: HomeAssistant,
) -> None:
    """Set up ffmpeg component test service start."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    await ffmpeg_dev.async_added_to_hass()

    async_start(hass, "test.ffmpeg_device")
    await hass.async_block_till_done()

    assert ffmpeg_dev.called_start
    assert ffmpeg_dev.called_entities == ["test.ffmpeg_device"]


async def test_async_get_image_with_width_height(hass: HomeAssistant) -> None:
    """Test fetching an image with a specific width and height."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    get_image_mock = AsyncMock()
    with patch(
        "homeassistant.components.ffmpeg.ImageFrame",
        return_value=Mock(get_image=get_image_mock),
    ):
        await ffmpeg.async_get_image(hass, "rtsp://fake", width=640, height=480)

    assert get_image_mock.call_args_list == [
        call("rtsp://fake", output_format="mjpeg", extra_cmd="-s 640x480")
    ]


async def test_async_get_image_with_extra_cmd_overlapping_width_height(
    hass: HomeAssistant,
) -> None:
    """Test fetching an image with and extra_cmd with width and height and a specific width and height."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    get_image_mock = AsyncMock()
    with patch(
        "homeassistant.components.ffmpeg.ImageFrame",
        return_value=Mock(get_image=get_image_mock),
    ):
        await ffmpeg.async_get_image(
            hass, "rtsp://fake", extra_cmd="-s 1024x768", width=640, height=480
        )

    assert get_image_mock.call_args_list == [
        call("rtsp://fake", output_format="mjpeg", extra_cmd="-s 1024x768")
    ]


async def test_async_get_image_with_extra_cmd_width_height(hass: HomeAssistant) -> None:
    """Test fetching an image with and extra_cmd and a specific width and height."""
    with assert_setup_component(1):
        await async_setup_component(hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    get_image_mock = AsyncMock()
    with patch(
        "homeassistant.components.ffmpeg.ImageFrame",
        return_value=Mock(get_image=get_image_mock),
    ):
        await ffmpeg.async_get_image(
            hass, "rtsp://fake", extra_cmd="-vf any", width=640, height=480
        )

    assert get_image_mock.call_args_list == [
        call("rtsp://fake", output_format="mjpeg", extra_cmd="-vf any -s 640x480")
    ]
