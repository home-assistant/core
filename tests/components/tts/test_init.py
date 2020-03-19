"""The tests for the TTS component."""
import ctypes
import os
import shutil
from unittest.mock import PropertyMock, patch

import pytest
import requests

from homeassistant.components.demo.tts import DemoProvider
import homeassistant.components.http as http
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    MEDIA_TYPE_MUSIC,
    SERVICE_PLAY_MEDIA,
)
import homeassistant.components.tts as tts
from homeassistant.setup import async_setup_component, setup_component

from tests.common import (
    assert_setup_component,
    get_test_home_assistant,
    get_test_instance_port,
    mock_service,
    mock_storage,
)


@pytest.fixture(autouse=True)
def mutagen_mock():
    """Mock writing tags."""
    with patch(
        "homeassistant.components.tts.SpeechManager.write_tags",
        side_effect=lambda *args: args[1],
    ):
        yield


class TestTTS:
    """Test the Google speech component."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.demo_provider = DemoProvider("en")
        self.default_tts_cache = self.hass.config.path(tts.DEFAULT_CACHE_DIR)
        self.mock_storage = mock_storage()
        self.mock_storage.__enter__()

        setup_component(
            self.hass,
            http.DOMAIN,
            {http.DOMAIN: {http.CONF_SERVER_PORT: get_test_instance_port()}},
        )

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()
        self.mock_storage.__exit__(None, None, None)

        if os.path.isdir(self.default_tts_cache):
            shutil.rmtree(self.default_tts_cache)

    def test_setup_component_demo(self):
        """Set up the demo platform with defaults."""
        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        assert self.hass.services.has_service(tts.DOMAIN, "demo_say")
        assert self.hass.services.has_service(tts.DOMAIN, "clear_cache")

    @patch("os.mkdir", side_effect=OSError(2, "No access"))
    def test_setup_component_demo_no_access_cache_folder(self, mock_mkdir):
        """Set up the demo platform with defaults."""
        config = {tts.DOMAIN: {"platform": "demo"}}

        assert not setup_component(self.hass, tts.DOMAIN, config)

        assert not self.hass.services.has_service(tts.DOMAIN, "demo_say")
        assert not self.hass.services.has_service(tts.DOMAIN, "clear_cache")

    def test_setup_component_and_test_service(self):
        """Set up the demo platform and call service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
        assert calls[0].data[
            ATTR_MEDIA_CONTENT_ID
        ] == "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3".format(
            self.hass.config.api.base_url
        )
        assert os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
            )
        )

    def test_setup_component_and_test_service_with_config_language(self):
        """Set up the demo platform and call service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo", "language": "de"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
        assert calls[0].data[
            ATTR_MEDIA_CONTENT_ID
        ] == "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3".format(
            self.hass.config.api.base_url
        )
        assert os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3",
            )
        )

    def test_setup_component_and_test_service_with_wrong_conf_language(self):
        """Set up the demo platform and call service with wrong config."""
        config = {tts.DOMAIN: {"platform": "demo", "language": "ru"}}

        with assert_setup_component(0, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

    def test_setup_component_and_test_service_with_service_language(self):
        """Set up the demo platform and call service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
        assert calls[0].data[
            ATTR_MEDIA_CONTENT_ID
        ] == "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3".format(
            self.hass.config.api.base_url
        )
        assert os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3",
            )
        )

    def test_setup_component_test_service_with_wrong_service_language(self):
        """Set up the demo platform and call service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "lang",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 0
        assert not os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_lang_-_demo.mp3",
            )
        )

    def test_setup_component_and_test_service_with_service_options(self):
        """Set up the demo platform and call service with options."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
                tts.ATTR_OPTIONS: {"voice": "alex"},
            },
        )
        self.hass.block_till_done()

        opt_hash = ctypes.c_size_t(hash(frozenset({"voice": "alex"}))).value

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
        assert calls[0].data[
            ATTR_MEDIA_CONTENT_ID
        ] == "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{}_demo.mp3".format(
            self.hass.config.api.base_url, opt_hash
        )
        assert os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{0}_demo.mp3".format(
                    opt_hash
                ),
            )
        )

    @patch(
        "homeassistant.components.demo.tts.DemoProvider.default_options",
        new_callable=PropertyMock(return_value={"voice": "alex"}),
    )
    def test_setup_component_and_test_with_service_options_def(self, def_mock):
        """Set up the demo platform and call service with default options."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
            },
        )
        self.hass.block_till_done()

        opt_hash = ctypes.c_size_t(hash(frozenset({"voice": "alex"}))).value

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
        assert calls[0].data[
            ATTR_MEDIA_CONTENT_ID
        ] == "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{}_demo.mp3".format(
            self.hass.config.api.base_url, opt_hash
        )
        assert os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{0}_demo.mp3".format(
                    opt_hash
                ),
            )
        )

    def test_setup_component_and_test_service_with_service_options_wrong(self):
        """Set up the demo platform and call service with wrong options."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
                tts.ATTR_OPTIONS: {"speed": 1},
            },
        )
        self.hass.block_till_done()

        opt_hash = ctypes.c_size_t(hash(frozenset({"speed": 1}))).value

        assert len(calls) == 0
        assert not os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{0}_demo.mp3".format(
                    opt_hash
                ),
            )
        )

    def test_setup_component_and_test_service_with_base_url_set(self):
        """Set up the demo platform with ``base_url`` set and call service."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo", "base_url": "http://fnord"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_MUSIC
        assert (
            calls[0].data[ATTR_MEDIA_CONTENT_ID] == "http://fnord"
            "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
            "_en_-_demo.mp3"
        )

    def test_setup_component_and_test_service_clear_cache(self):
        """Set up the demo platform and call service clear cache."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
            )
        )

        self.hass.services.call(tts.DOMAIN, tts.SERVICE_CLEAR_CACHE, {})
        self.hass.block_till_done()

        assert not os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
            )
        )

    def test_setup_component_and_test_service_with_receive_voice(self):
        """Set up the demo platform and call service and receive voice."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.start()

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        req = requests.get(calls[0].data[ATTR_MEDIA_CONTENT_ID])
        _, demo_data = self.demo_provider.get_tts_audio("bla", "en")
        demo_data = tts.SpeechManager.write_tags(
            "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
            demo_data,
            self.demo_provider,
            "AI person is in front of your door.",
            "en",
            None,
        )
        assert req.status_code == 200
        assert req.content == demo_data

    def test_setup_component_and_test_service_with_receive_voice_german(self):
        """Set up the demo platform and call service and receive voice."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo", "language": "de"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.start()

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        req = requests.get(calls[0].data[ATTR_MEDIA_CONTENT_ID])
        _, demo_data = self.demo_provider.get_tts_audio("bla", "de")
        demo_data = tts.SpeechManager.write_tags(
            "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3",
            demo_data,
            self.demo_provider,
            "There is someone at the door.",
            "de",
            None,
        )
        assert req.status_code == 200
        assert req.content == demo_data

    def test_setup_component_and_web_view_wrong_file(self):
        """Set up the demo platform and receive wrong file from web."""
        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.start()

        url = (
            "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
        ).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 404

    def test_setup_component_and_web_view_wrong_filename(self):
        """Set up the demo platform and receive wrong filename from web."""
        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.start()

        url = (
            "{}/api/tts_proxy/265944dsk32c1b2a621be5930510bb2cd_en_-_demo.mp3"
        ).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 404

    def test_setup_component_test_without_cache(self):
        """Set up demo platform without cache."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo", "cache": False}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert not os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
            )
        )

    def test_setup_component_test_with_cache_call_service_without_cache(self):
        """Set up demo platform with cache and call service without cache."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo", "cache": True}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_CACHE: False,
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert not os.path.isfile(
            os.path.join(
                self.default_tts_cache,
                "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
            )
        )

    def test_setup_component_test_with_cache_dir(self):
        """Set up demo platform with cache and call service without cache."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        _, demo_data = self.demo_provider.get_tts_audio("bla", "en")
        cache_file = os.path.join(
            self.default_tts_cache,
            "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
        )

        os.mkdir(self.default_tts_cache)
        with open(cache_file, "wb") as voice_file:
            voice_file.write(demo_data)

        config = {tts.DOMAIN: {"platform": "demo", "cache": True}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        with patch(
            "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
            return_value=(None, None),
        ):
            self.hass.services.call(
                tts.DOMAIN,
                "demo_say",
                {
                    "entity_id": "media_player.something",
                    tts.ATTR_MESSAGE: "There is someone at the door.",
                },
            )
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0].data[
            ATTR_MEDIA_CONTENT_ID
        ] == "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3".format(
            self.hass.config.api.base_url
        )

    @patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=(None, None),
    )
    def test_setup_component_test_with_error_on_get_tts(self, tts_mock):
        """Set up demo platform with wrong get_tts_audio."""
        calls = mock_service(self.hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

        config = {tts.DOMAIN: {"platform": "demo"}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.services.call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        )
        self.hass.block_till_done()

        assert len(calls) == 0

    def test_setup_component_load_cache_retrieve_without_mem_cache(self):
        """Set up component and load cache and get without mem cache."""
        _, demo_data = self.demo_provider.get_tts_audio("bla", "en")
        cache_file = os.path.join(
            self.default_tts_cache,
            "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
        )

        os.mkdir(self.default_tts_cache)
        with open(cache_file, "wb") as voice_file:
            voice_file.write(demo_data)

        config = {tts.DOMAIN: {"platform": "demo", "cache": True}}

        with assert_setup_component(1, tts.DOMAIN):
            setup_component(self.hass, tts.DOMAIN, config)

        self.hass.start()

        url = (
            "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
        ).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 200
        assert req.content == demo_data


async def test_setup_component_and_web_get_url(hass, hass_client):
    """Set up the demo platform and receive file from web."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_get_url"
    data = {"platform": "demo", "message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == 200
    response = await req.json()
    assert response.get("url") == (
        "{}/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3".format(
            hass.config.api.base_url
        )
    )

    tts_cache = hass.config.path(tts.DEFAULT_CACHE_DIR)
    if os.path.isdir(tts_cache):
        shutil.rmtree(tts_cache)


async def test_setup_component_and_web_get_url_bad_config(hass, hass_client):
    """Set up the demo platform and receive wrong file from web."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_get_url"
    data = {"message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == 400
