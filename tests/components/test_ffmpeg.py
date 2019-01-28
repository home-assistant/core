"""The tests for Home Assistant ffmpeg."""
import asyncio
from unittest.mock import MagicMock

import homeassistant.components.ffmpeg as ffmpeg
from homeassistant.components.ffmpeg import (
    DOMAIN, SERVICE_RESTART, SERVICE_START, SERVICE_STOP)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.setup import setup_component, async_setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)


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

    def __init__(self, hass, initial_state=True,
                 entity_id='test.ffmpeg_device'):
        """Initialize mock."""
        super().__init__(initial_state)

        self.hass = hass
        self.entity_id = entity_id
        self.ffmpeg = MagicMock
        self.called_stop = False
        self.called_start = False
        self.called_restart = False
        self.called_entities = None

    @asyncio.coroutine
    def _async_start_ffmpeg(self, entity_ids):
        """Mock start."""
        self.called_start = True
        self.called_entities = entity_ids

    @asyncio.coroutine
    def _async_stop_ffmpeg(self, entity_ids):
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

        assert self.hass.data[ffmpeg.DATA_FFMPEG].binary == 'ffmpeg'

    def test_setup_component_test_service(self):
        """Set up ffmpeg component test services."""
        with assert_setup_component(1):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        assert self.hass.services.has_service(ffmpeg.DOMAIN, 'start')
        assert self.hass.services.has_service(ffmpeg.DOMAIN, 'stop')
        assert self.hass.services.has_service(ffmpeg.DOMAIN, 'restart')


@asyncio.coroutine
def test_setup_component_test_register(hass):
    """Set up ffmpeg component test register."""
    with assert_setup_component(1):
        yield from async_setup_component(
            hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    hass.bus.async_listen_once = MagicMock()
    ffmpeg_dev = MockFFmpegDev(hass)
    yield from ffmpeg_dev.async_added_to_hass()

    assert hass.bus.async_listen_once.called
    assert hass.bus.async_listen_once.call_count == 2


@asyncio.coroutine
def test_setup_component_test_register_no_startup(hass):
    """Set up ffmpeg component test register without startup."""
    with assert_setup_component(1):
        yield from async_setup_component(
            hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    hass.bus.async_listen_once = MagicMock()
    ffmpeg_dev = MockFFmpegDev(hass, False)
    yield from ffmpeg_dev.async_added_to_hass()

    assert hass.bus.async_listen_once.called
    assert hass.bus.async_listen_once.call_count == 1


@asyncio.coroutine
def test_setup_component_test_service_start(hass):
    """Set up ffmpeg component test service start."""
    with assert_setup_component(1):
        yield from async_setup_component(
            hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    yield from ffmpeg_dev.async_added_to_hass()

    async_start(hass)
    yield from hass.async_block_till_done()

    assert ffmpeg_dev.called_start


@asyncio.coroutine
def test_setup_component_test_service_stop(hass):
    """Set up ffmpeg component test service stop."""
    with assert_setup_component(1):
        yield from async_setup_component(
            hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    yield from ffmpeg_dev.async_added_to_hass()

    async_stop(hass)
    yield from hass.async_block_till_done()

    assert ffmpeg_dev.called_stop


@asyncio.coroutine
def test_setup_component_test_service_restart(hass):
    """Set up ffmpeg component test service restart."""
    with assert_setup_component(1):
        yield from async_setup_component(
            hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    yield from ffmpeg_dev.async_added_to_hass()

    async_restart(hass)
    yield from hass.async_block_till_done()

    assert ffmpeg_dev.called_stop
    assert ffmpeg_dev.called_start


@asyncio.coroutine
def test_setup_component_test_service_start_with_entity(hass):
    """Set up ffmpeg component test service start."""
    with assert_setup_component(1):
        yield from async_setup_component(
            hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

    ffmpeg_dev = MockFFmpegDev(hass, False)
    yield from ffmpeg_dev.async_added_to_hass()

    async_start(hass, 'test.ffmpeg_device')
    yield from hass.async_block_till_done()

    assert ffmpeg_dev.called_start
    assert ffmpeg_dev.called_entities == ['test.ffmpeg_device']
