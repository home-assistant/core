"""Fixtures for the Bosch Smart Home Camera integration tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.bosch_shc_camera.const import DEFAULT_OPTIONS, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant

from . import TEST_BEARER_TOKEN, TEST_REFRESH_TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry matching the real config-entry data shape.

    Data keys mirror exactly what `config_flow.py`'s `async_oauth_create_entry`
    / `async_step_manual_paste` write via `async_create_entry`. `version=3`
    matches `BoschCameraConfigFlow.VERSION` so tests don't exercise
    `async_migrate_entry` unless they explicitly want to (construct a
    lower-versioned entry directly in that case).
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bosch Smart Home Camera",
        unique_id=DOMAIN,
        version=3,
        data={
            "bearer_token": TEST_BEARER_TOKEN,
            "refresh_token": TEST_REFRESH_TOKEN,
        },
        options=dict(DEFAULT_OPTIONS),
    )


@pytest.fixture(autouse=True)
def aioclient_mock(hass: HomeAssistant) -> Generator[AiohttpClientMocker]:
    """Route every Bosch cloud/OAuth HTTP call through an `AiohttpClientMocker`.

    Overrides the core `aioclient_mock` fixture (same pattern as
    `tests/components/rainbird/conftest.py`) because this integration never
    uses HA's standard `async_get_clientsession(hass)` for Bosch traffic —
    `cloud_ssl.async_get_bosch_cloud_session` builds its own dedicated
    `aiohttp.ClientSession` (pinning Bosch's private CA, see `cloud_ssl.py`).
    That single function is the real third-party-library boundary: the
    OAuth2 token exchange (`config_flow.BoschOAuth2Implementation`/
    `_exchange_code`/`_do_refresh`) and every cloud REST call the coordinator
    makes (`/v11/video_inputs`, `/v11/feature_flags`, `/protocol_support`,
    ...) all resolve their session through it.

    It is imported by value (`from .cloud_ssl import
    async_get_bosch_cloud_session`) into both `config_flow.py` and the
    package's own `__init__.py` (re-exported for `coordinator.py`'s
    call-time `from . import async_get_bosch_cloud_session`) — patching only
    `cloud_ssl.async_get_bosch_cloud_session` would miss both of those
    already-bound names, so all three call sites are patched to the same
    mocked session.
    """
    mocker = AiohttpClientMocker()
    cached_session: list[object] = []

    def create_session(_hass: HomeAssistant) -> object:
        if cached_session:
            return cached_session[0]
        session = mocker.create_session(hass.loop)
        cached_session.append(session)

        async def close_session(_event: object) -> None:
            await session.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, close_session)
        return session

    with (
        patch(
            "homeassistant.components.bosch_shc_camera.cloud_ssl.async_get_bosch_cloud_session",
            side_effect=create_session,
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.async_get_bosch_cloud_session",
            side_effect=create_session,
        ),
        patch(
            "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
            side_effect=create_session,
        ),
    ):
        yield mocker
