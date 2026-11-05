"""Fixtures for the Voice app: a stand-in for the app itself."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.hassio import AddonInfo, AddonState
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.voice_support.app import DiscoveredApp
from homeassistant.components.voice_support.const import (
    API_VERSION,
    DOMAIN,
    PREVIEW_FEATURE_WAKE_WORD_VERIFICATION,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

WAKE_WORDS = [{"id": "okay_nabu", "phrase": "okay nabu"}]


class FakeApp:
    """The app, as far as the integration can tell.

    It answers /info with whatever the test set, and /run by sending back
    the events the test wrote down, each after that many chunks of audio
    have arrived. That is where the parts worth testing are: audio going in
    while answers come back on their own schedule.
    """

    def __init__(self) -> None:
        """Set up an app that accepts every wake word at once."""
        self.info: dict = {
            "api_version": API_VERSION,
            "name": "Voice",
            "version": "0.1.0",
            "max_run_ms": 30000,
            "wake_words": WAKE_WORDS,
        }
        self.events: list[tuple[int, dict]] = [
            (
                0,
                {
                    "type": "wake-word-end",
                    "wake_word_output": {
                        "wake_word_phrase": "okay nabu",
                        "wake_word_audio_ms": 1000,
                    },
                },
            )
        ]
        """What to say, and after how many chunks of audio to say it."""

        self.requests: list[dict] = []
        self.audio: list[bytes] = []
        """The whole of each run's audio, in order."""
        self.audio_ended = False

        self.server: TestServer | None = None
        self.port: int | None = None
        """Where it last served, so it can come back to the same address."""

    async def start(self) -> tuple[str, int]:
        """Start serving, and say where."""
        app = web.Application()
        app.add_routes([web.get("/info", self._info), web.get("/run", self._run)])
        self.server = TestServer(app, port=self.port)
        await self.server.start_server()
        self.port = self.server.port
        return self.server.host, self.server.port

    async def stop(self) -> None:
        """Stop serving."""
        if self.server is not None:
            await self.server.close()
            self.server = None

    async def _info(self, request: web.Request) -> web.Response:
        return web.json_response(self.info)

    async def _run(self, request: web.Request) -> web.WebSocketResponse:
        websocket = web.WebSocketResponse()
        await websocket.prepare(request)

        audio = bytearray()
        chunks = 0
        due = list(self.events)

        async def _say_what_is_due() -> None:
            while due and (due[0][0] <= chunks):
                await websocket.send_json(due.pop(0)[1])

        await _say_what_is_due()

        async for message in websocket:
            if message.type == WSMsgType.BINARY:
                audio.extend(message.data)
                chunks += 1
                await _say_what_is_due()
                continue
            if message.type != WSMsgType.TEXT:
                continue

            event = json.loads(message.data)
            if event["type"] == "run-start":
                self.requests.append(event)
            elif event["type"] == "audio-end":
                self.audio_ended = True
                break

        self.audio.append(bytes(audio))
        await websocket.close()
        return websocket


@pytest.fixture(autouse=True)
async def core_components(hass: HomeAssistant) -> None:
    """Set up what the pipeline's own dependencies need."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "labs", {})


@pytest.fixture
async def verification_enabled(hass: HomeAssistant) -> None:
    """Turn on the Labs preview feature that asks the app anything."""
    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, True
    )


@pytest.fixture
async def fake_app() -> AsyncGenerator[FakeApp]:
    """A running stand-in for the app."""
    app = FakeApp()
    await app.start()
    yield app
    await app.stop()


@pytest.fixture
def config_entry_for() -> Callable[[FakeApp], MockConfigEntry]:
    """Make a config entry pointing at a fake app."""

    def _make(app: FakeApp) -> MockConfigEntry:
        assert app.server is not None
        return MockConfigEntry(
            domain=DOMAIN,
            unique_id="0123456789abcdef",
            title="Voice",
            data={CONF_HOST: app.server.host, CONF_PORT: app.server.port},
        )

    return _make


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    fake_app: FakeApp,
    config_entry_for: Callable[[FakeApp], MockConfigEntry],
    verification_enabled: None,
) -> MockConfigEntry:
    """Set up the integration against the fake app."""
    entry = config_entry_for(fake_app)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def app_manager() -> Generator[MagicMock]:
    """Stand in for the Supervisor's view of the app.

    It starts out installed and running, which is the case where nothing has
    to be installed; tests that want the other cases set `app_info.state`.
    """
    manager = MagicMock()
    manager.async_get_addon_info = AsyncMock(
        return_value=AddonInfo(
            available=True,
            hostname="f1b2c3d4-voice",
            options={},
            state=AddonState.RUNNING,
            update_available=False,
            version="0.1.0",
        )
    )
    manager.async_start_addon = AsyncMock()
    with (
        patch(
            "homeassistant.components.voice_support.config_flow.get_app_manager",
            return_value=manager,
        ),
        patch(
            "homeassistant.components.voice_support.config_flow.is_hassio",
            return_value=True,
        ),
    ):
        yield manager


@pytest.fixture
def install_app(hass: HomeAssistant, app_manager: MagicMock) -> MagicMock:
    """Make installing the app succeed, and record that it happened."""

    async def _install() -> None:
        # Yield, so the flow shows its progress step rather than racing past it.
        await asyncio.sleep(0)
        app_manager.async_get_addon_info.return_value.state = AddonState.NOT_RUNNING

    app_manager.async_schedule_install_addon = MagicMock(
        side_effect=lambda *_, **__: hass.async_create_task(_install())
    )
    return app_manager.async_schedule_install_addon


@pytest.fixture
def discovered_app() -> Generator[AsyncMock]:
    """Make the app announce itself as soon as it is started."""
    app = DiscoveredApp(uuid="0123456789abcdef", host="f1b2c3d4-voice", port=10800)
    with (
        patch(
            "homeassistant.components.voice_support.config_flow.async_wait_for_discovery",
            AsyncMock(return_value=app),
        ) as wait,
        patch(
            "homeassistant.components.voice_support.config_flow.async_get_discovery",
            AsyncMock(return_value=app),
        ),
    ):
        yield wait
