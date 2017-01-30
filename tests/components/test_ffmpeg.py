"""The tests for Home Assistant ffmpeg."""
import asyncio
from unittest.mock import patch, MagicMock

import homeassistant.components.ffmpeg as ffmpeg
from homeassistant.bootstrap import setup_component
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)

from tests.common import (
    get_test_home_assistant, assert_setup_component, load_fixture, mock_coro)


class MockFFmpegDev(ffmpeg.FFmpegBase):
    """FFmpeg device mock."""

    def __init__(self, initial_state=True, entity_id='test.ffmpeg_device'):
        """Initialize mock."""
        super().__init__(initial_state)

        self.entity_id = entity_id
        self.ffmpeg = MagicMock
        self.called_stop = False
        self.called_start = False
        self.called_restart = False

    @asyncio.coroutine
    def async_start_ffmpeg(self):
        """Mock start."""
        self.called_start = True

    @asyncio.coroutine
    def async_stop_ffmpeg(self):
        """Mock stop."""
        self.called_stop = True

    @asyncio.coroutine
    def async_restart_ffmpeg(self):
        """Mock restart."""
        self.called_restart = True


class TestFFmpegSetup(object):
    """Test class for ffmpeg."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Setup ffmpeg component."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        assert self.hass.data[ffmpeg.DATA_FFMPEG].binary == 'ffmpeg'

    def test_setup_component_test_service(self):
        """Setup ffmpeg component test services."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        assert self.hass.services.has_service(ffmpeg.DOMAIN, 'start')
        assert self.hass.services.has_service(ffmpeg.DOMAIN, 'stop')
        assert self.hass.services.has_service(ffmpeg.DOMAIN, 'restart')

    def test_setup_component_test_register(self):
        """Setup ffmpeg component test register."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        self.hass.bus.async_listen_once = MagicMock()
        ffmpeg_dev = MockFFmpegDev()

        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        run_callback_threadsafe(
            self.hass.loop, manager.async_register_device, ffmpeg_dev).result()

        assert self.hass.bus.async_listen_once.called
        assert self.hass.bus.async_listen_once.call_count == 2

    def test_setup_component_test_register_no_startup(self):
        """Setup ffmpeg component test register without startup."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        self.hass.bus.async_listen_once = MagicMock()
        ffmpeg_dev = MockFFmpegDev(False)

        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        run_callback_threadsafe(
            self.hass.loop, manager.async_register_device, ffmpeg_dev).result()

        assert self.hass.bus.async_listen_once.called
        assert self.hass.bus.async_listen_once.call_count == 1

    def test_setup_component_test_servcie_start(self):
        """Setup ffmpeg component test service start."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        ffmpeg_dev = MockFFmpegDev(False)
        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        run_callback_threadsafe(
            self.hass.loop, manager.async_register_device, ffmpeg_dev).result()

        ffmpeg.start(self.hass)
        self.hass.block_till_done()

        assert ffmpeg_dev.called_start

    def test_setup_component_test_servcie_stop(self):
        """Setup ffmpeg component test service stop."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        ffmpeg_dev = MockFFmpegDev(False)
        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        run_callback_threadsafe(
            self.hass.loop, manager.async_register_device, ffmpeg_dev).result()

        ffmpeg.stop(self.hass)
        self.hass.block_till_done()

        assert ffmpeg_dev.called_stop

    def test_setup_component_test_servcie_restart(self):
        """Setup ffmpeg component test service restart."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        ffmpeg_dev = MockFFmpegDev(False)
        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        run_callback_threadsafe(
            self.hass.loop, manager.async_register_device, ffmpeg_dev).result()

        ffmpeg.restart(self.hass)
        self.hass.block_till_done()

        assert ffmpeg_dev.called_restart

    def test_setup_component_test_servcie_start_with_entity(self):
        """Setup ffmpeg component test service start."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        ffmpeg_dev = MockFFmpegDev(False)
        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        run_callback_threadsafe(
            self.hass.loop, manager.async_register_device, ffmpeg_dev).result()

        ffmpeg.start(self.hass, 'test.ffmpeg_device')
        self.hass.block_till_done()

        assert ffmpeg_dev.called_start

    def test_setup_component_test_run_test_false(self):
        """Setup ffmpeg component test run_test false."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {
                'run_test': False,
            }})

        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        assert run_coroutine_threadsafe(
            manager.async_run_test("blabalblabla"), self.hass.loop).result()
        assert len(manager._cache) == 0

    @patch('haffmpeg.Test.run_test',
           return_value=mock_coro(return_value=True)())
    def test_setup_component_test_run_test(self, mock_test):
        """Setup ffmpeg component test run_test."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        assert run_coroutine_threadsafe(
            manager.async_run_test("blabalblabla"), self.hass.loop).result()
        assert mock_test.called
        assert mock_test.call_count == 1
        assert len(manager._cache) == 1
        assert manager._cache['blabalblabla']

        assert run_coroutine_threadsafe(
            manager.async_run_test("blabalblabla"), self.hass.loop).result()
        assert mock_test.called
        assert mock_test.call_count == 1
        assert len(manager._cache) == 1
        assert manager._cache['blabalblabla']

    @patch('haffmpeg.Test.run_test',
           return_value=mock_coro(return_value=False)())
    def test_setup_component_test_run_test_test_fail(self, mock_test):
        """Setup ffmpeg component test run_test."""
        with assert_setup_component(2):
            setup_component(self.hass, ffmpeg.DOMAIN, {ffmpeg.DOMAIN: {}})

        manager = self.hass.data[ffmpeg.DATA_FFMPEG]

        assert not run_coroutine_threadsafe(
            manager.async_run_test("blabalblabla"), self.hass.loop).result()
        assert mock_test.called
        assert mock_test.call_count == 1
        assert len(manager._cache) == 1
        assert not manager._cache['blabalblabla']

        assert not run_coroutine_threadsafe(
            manager.async_run_test("blabalblabla"), self.hass.loop).result()
        assert mock_test.called
        assert mock_test.call_count == 1
        assert len(manager._cache) == 1
        assert not manager._cache['blabalblabla']
