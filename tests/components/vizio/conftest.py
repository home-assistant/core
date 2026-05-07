"""Configure py.test."""

from collections.abc import Generator
from http import HTTPStatus
import re
from typing import Any
from unittest.mock import patch

import pytest
from pyvizio.api._protocol import ENDPOINT
from yarl import URL

from homeassistant.components.vizio.const import DOMAIN

from .common import load_fixture, settings_options_url, settings_url, url_for
from .const import (
    APP_LIST,
    HOST,
    HOST2,
    MOCK_SPEAKER_CONFIG,
    MOCK_USER_VALID_TV_CONFIG,
    UNIQUE_ID,
    ZEROCONF_HOST,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


@pytest.fixture
def mock_tv_config_entry() -> MockConfigEntry:
    """Return a mock TV config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_VALID_TV_CONFIG,
        unique_id=UNIQUE_ID,
    )


@pytest.fixture
def mock_speaker_config_entry() -> MockConfigEntry:
    """Return a mock speaker config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SPEAKER_CONFIG,
        unique_id=UNIQUE_ID,
    )


# ---------------------------------------------------------------------------
# Internal building blocks for the fixtures below.
# ---------------------------------------------------------------------------


def _register_endpoint_500(
    aioclient_mock: AiohttpClientMocker, host: str, device_class: str, key: str
) -> None:
    """Register a state endpoint to return HTTP 500 (pyvizio returns ``None``)."""
    aioclient_mock.get(
        url_for(host, device_class, key), status=HTTPStatus.INTERNAL_SERVER_ERROR
    )


def _register_common_endpoints(
    aioclient_mock: AiohttpClientMocker, host: str, device_class: str
) -> None:
    """Register endpoints identical across healthy-state scenarios.

    Covers DEVICE_INFO, VERSION (+ alt), SERIAL_NUMBER (+ alt). Every
    healthy scenario serves the same payload here.
    """
    aioclient_mock.get(
        url_for(host, device_class, "DEVICE_INFO"), json=load_fixture("device_info")
    )
    version = load_fixture("version")
    aioclient_mock.get(url_for(host, device_class, "VERSION"), json=version)
    aioclient_mock.get(url_for(host, device_class, "_ALT_VERSION"), json=version)
    serial = load_fixture("serial_number")
    aioclient_mock.get(url_for(host, device_class, "SERIAL_NUMBER"), json=serial)
    aioclient_mock.get(url_for(host, device_class, "_ALT_SERIAL_NUMBER"), json=serial)


async def _setting_probe_response(
    method: str, url: URL, data: Any
) -> AiohttpClientMockResponse:
    """Build a single-item GET response with cname matching the URL tail.

    Pyvizio's ``set_setting`` first GETs the individual setting to obtain
    a HASHVAL and matches the response item by ``CNAME`` against the
    requested setting name. We synthesize the response per request URL.
    """
    setting_name = url.parts[-1]
    return AiohttpClientMockResponse(
        method=method,
        url=url,
        json={
            "STATUS": {"RESULT": "SUCCESS", "DETAIL": "Success"},
            "ITEMS": [
                {
                    "CNAME": setting_name,
                    "TYPE": "T_LIST_V1",
                    "NAME": setting_name,
                    "VALUE": "value",
                    "HASHVAL": 1,
                }
            ],
        },
    )


def _register_action_endpoints(
    aioclient_mock: AiohttpClientMocker, host: str, device_class: str
) -> None:
    """Register PUT endpoints used by integration actions.

    Returns empty success envelopes so action methods complete; tests
    inspect ``aioclient_mock.mock_calls`` to verify which request was made.
    """
    success = load_fixture("empty_success")
    aioclient_mock.put(url_for(host, device_class, "KEY_PRESS"), json=success)
    aioclient_mock.put(url_for(host, device_class, "CURRENT_INPUT"), json=success)
    if device_class == "tv":
        aioclient_mock.put(url_for(host, device_class, "LAUNCH_APP"), json=success)
    settings_pattern = (
        rf"https://{re.escape(host)}"
        rf"{re.escape(ENDPOINT[device_class]['SETTINGS'])}/[^/]+/[^/]+"
    )
    aioclient_mock.put(re.compile(settings_pattern), json=success)
    aioclient_mock.get(
        re.compile(settings_pattern), side_effect=_setting_probe_response
    )


# ---------------------------------------------------------------------------
# Apps catalog + delays — neither is part of the device wire protocol so
# they're patched at the integration boundary instead of HTTP-mocked.
# ---------------------------------------------------------------------------


@pytest.fixture(name="vizio_data_coordinator_update", autouse=True)
def vizio_data_coordinator_update_fixture() -> Generator[None]:
    """Mock the external apps catalog (not a device endpoint)."""
    with patch(
        "homeassistant.components.vizio.coordinator.gen_apps_list_from_url",
        return_value=APP_LIST,
    ):
        yield


@pytest.fixture(name="vizio_data_coordinator_update_failure")
def vizio_data_coordinator_update_failure_fixture() -> Generator[None]:
    """Mock apps catalog fetch returning None."""
    with patch(
        "homeassistant.components.vizio.coordinator.gen_apps_list_from_url",
        return_value=None,
    ):
        yield


@pytest.fixture(autouse=True)
def no_delay_secs() -> Generator[None]:
    """Patch default delay between remote command repeats to 0."""
    with patch("homeassistant.components.vizio.remote.DEFAULT_DELAY_SECS", 0):
        yield


# ---------------------------------------------------------------------------
# Config-flow probe fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture(name="vizio_connect")
def vizio_connect_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Healthy device: get_unique_id and validate_ha_config both succeed."""
    serial = load_fixture("serial_number")
    audio_tv = load_fixture("audio_settings")
    audio_speaker = load_fixture("audio_settings_speaker")
    for host in (HOST, HOST2):
        for device_class in ("tv", "speaker"):
            aioclient_mock.get(
                url_for(host, device_class, "SERIAL_NUMBER"), json=serial
            )
            aioclient_mock.get(
                url_for(host, device_class, "_ALT_SERIAL_NUMBER"), json=serial
            )
        aioclient_mock.get(settings_url(host, "tv", "audio"), json=audio_tv)
        aioclient_mock.get(settings_url(host, "speaker", "audio"), json=audio_speaker)


@pytest.fixture(name="vizio_no_unique_id")
def vizio_no_unique_id_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Device returns no serial number — get_unique_id returns None."""
    for host in (HOST, HOST2):
        for device_class in ("tv", "speaker"):
            _register_endpoint_500(aioclient_mock, host, device_class, "SERIAL_NUMBER")
            _register_endpoint_500(
                aioclient_mock, host, device_class, "_ALT_SERIAL_NUMBER"
            )


@pytest.fixture(name="vizio_cant_connect")
def vizio_cant_connect_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Serial-number probe succeeds; validation + state probes all fail."""
    serial = load_fixture("serial_number")
    state_keys = (
        "POWER_MODE",
        "DEVICE_INFO",
        "VERSION",
        "_ALT_VERSION",
        "INPUTS",
        "CURRENT_INPUT",
    )
    for host in (HOST, HOST2):
        for device_class in ("tv", "speaker"):
            aioclient_mock.get(
                url_for(host, device_class, "SERIAL_NUMBER"), json=serial
            )
            aioclient_mock.get(
                url_for(host, device_class, "_ALT_SERIAL_NUMBER"), json=serial
            )
            aioclient_mock.get(
                settings_url(host, device_class, "audio"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            aioclient_mock.get(
                settings_options_url(host, device_class, "audio"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            for key in state_keys:
                _register_endpoint_500(aioclient_mock, host, device_class, key)
        _register_endpoint_500(aioclient_mock, host, "tv", "CURRENT_APP")


@pytest.fixture(name="vizio_complete_pairing")
def vizio_complete_pairing_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Pairing endpoints succeed end-to-end."""
    begin = load_fixture("pair_begin")
    finish = load_fixture("pair_finish")
    for host in (HOST, HOST2):
        for device_class in ("tv", "speaker"):
            aioclient_mock.put(url_for(host, device_class, "BEGIN_PAIR"), json=begin)
            aioclient_mock.put(url_for(host, device_class, "FINISH_PAIR"), json=finish)


@pytest.fixture(name="vizio_start_pairing_failure")
def vizio_start_pairing_failure_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Pairing /start returns 500."""
    finish = load_fixture("pair_finish")
    for host in (HOST, HOST2):
        for device_class in ("tv", "speaker"):
            aioclient_mock.put(
                url_for(host, device_class, "BEGIN_PAIR"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            aioclient_mock.put(url_for(host, device_class, "FINISH_PAIR"), json=finish)


@pytest.fixture(name="vizio_invalid_pin_failure")
def vizio_invalid_pin_failure_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Pairing /start succeeds; /pair returns 500 (pin rejected)."""
    begin = load_fixture("pair_begin")
    for host in (HOST, HOST2):
        for device_class in ("tv", "speaker"):
            aioclient_mock.put(url_for(host, device_class, "BEGIN_PAIR"), json=begin)
            aioclient_mock.put(
                url_for(host, device_class, "FINISH_PAIR"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )


# ---------------------------------------------------------------------------
# Pyvizio-internal helpers that don't accept an HA session.
# ---------------------------------------------------------------------------


@pytest.fixture(name="vizio_guess_device_type")
def vizio_guess_device_type_fixture() -> Generator[None]:
    """Stub pyvizio.async_guess_device_type (uses its own ClientSession)."""
    with patch(
        "homeassistant.components.vizio.config_flow.async_guess_device_type",
        return_value="speaker",
    ):
        yield


@pytest.fixture(name="vizio_hostname_check")
def vizio_hostname_check() -> Generator[None]:
    """Mock vizio hostname resolution (DNS, not pyvizio)."""
    with patch(
        "homeassistant.components.vizio.config_flow.socket.gethostbyname",
        return_value=ZEROCONF_HOST,
    ):
        yield


# ---------------------------------------------------------------------------
# Integration-setup bypass — HA layer.
# ---------------------------------------------------------------------------


@pytest.fixture(name="vizio_bypass_setup")
def vizio_bypass_setup_fixture() -> Generator[None]:
    """Bypass async_setup_entry entirely (HA-layer)."""
    with patch("homeassistant.components.vizio.async_setup_entry", return_value=True):
        yield


# ---------------------------------------------------------------------------
# State / coordinator fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture(name="vizio_bypass_update")
def vizio_bypass_update_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Device powers on but reports nothing else (every other endpoint 500s)."""
    serial = load_fixture("serial_number")
    audio_tv = load_fixture("audio_settings")
    audio_speaker = load_fixture("audio_settings_speaker")
    no_data_keys = ("DEVICE_INFO", "VERSION", "_ALT_VERSION", "INPUTS", "CURRENT_INPUT")
    for host in (HOST, HOST2):
        # Config-flow probes still succeed (some tests run user-step setup).
        for device_class in ("tv", "speaker"):
            aioclient_mock.get(
                url_for(host, device_class, "SERIAL_NUMBER"), json=serial
            )
            aioclient_mock.get(
                url_for(host, device_class, "_ALT_SERIAL_NUMBER"), json=serial
            )
        aioclient_mock.get(settings_url(host, "tv", "audio"), json=audio_tv)
        aioclient_mock.get(settings_url(host, "speaker", "audio"), json=audio_speaker)
        # Device is reachable for power; everything else fails.
        for device_class in ("tv", "speaker"):
            aioclient_mock.get(
                url_for(host, device_class, "POWER_MODE"), json=load_fixture("power_on")
            )
            for key in no_data_keys:
                _register_endpoint_500(aioclient_mock, host, device_class, key)
            aioclient_mock.get(
                settings_options_url(host, device_class, "audio"),
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        _register_endpoint_500(aioclient_mock, host, "tv", "CURRENT_APP")


@pytest.fixture(name="vizio_update")
def vizio_update_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """Healthy default state for both TV and speaker."""
    # TV: powered on, HDMI-1, no app running.
    aioclient_mock.get(url_for(HOST, "tv", "POWER_MODE"), json=load_fixture("power_on"))
    _register_common_endpoints(aioclient_mock, HOST, "tv")
    aioclient_mock.get(url_for(HOST, "tv", "INPUTS"), json=load_fixture("inputs_tv"))
    aioclient_mock.get(
        url_for(HOST, "tv", "CURRENT_INPUT"), json=load_fixture("current_input_hdmi1")
    )
    aioclient_mock.get(
        settings_url(HOST, "tv", "audio"), json=load_fixture("audio_settings")
    )
    aioclient_mock.get(
        settings_options_url(HOST, "tv", "audio"), json=load_fixture("audio_options")
    )
    aioclient_mock.get(
        url_for(HOST, "tv", "CURRENT_APP"), json=load_fixture("current_app_none")
    )
    _register_action_endpoints(aioclient_mock, HOST, "tv")

    # Speaker: powered on, HDMI-1.
    aioclient_mock.get(
        url_for(HOST, "speaker", "POWER_MODE"), json=load_fixture("power_on")
    )
    _register_common_endpoints(aioclient_mock, HOST, "speaker")
    aioclient_mock.get(
        url_for(HOST, "speaker", "INPUTS"), json=load_fixture("inputs_speaker")
    )
    aioclient_mock.get(
        url_for(HOST, "speaker", "CURRENT_INPUT"),
        json=load_fixture("current_input_speaker"),
    )
    aioclient_mock.get(
        settings_url(HOST, "speaker", "audio"),
        json=load_fixture("audio_settings_speaker"),
    )
    aioclient_mock.get(
        settings_options_url(HOST, "speaker", "audio"),
        json=load_fixture("audio_options"),
    )
    _register_action_endpoints(aioclient_mock, HOST, "speaker")


@pytest.fixture(name="vizio_update_with_apps")
def vizio_update_with_apps_fixture(aioclient_mock: AiohttpClientMocker) -> None:
    """TV with Hulu running on the smartcast input (CAST input present)."""
    aioclient_mock.get(url_for(HOST, "tv", "POWER_MODE"), json=load_fixture("power_on"))
    _register_common_endpoints(aioclient_mock, HOST, "tv")
    aioclient_mock.get(
        url_for(HOST, "tv", "INPUTS"), json=load_fixture("inputs_tv_with_cast")
    )
    aioclient_mock.get(
        url_for(HOST, "tv", "CURRENT_INPUT"), json=load_fixture("current_input_cast")
    )
    aioclient_mock.get(
        settings_url(HOST, "tv", "audio"), json=load_fixture("audio_settings")
    )
    aioclient_mock.get(
        settings_options_url(HOST, "tv", "audio"), json=load_fixture("audio_options")
    )
    aioclient_mock.get(
        url_for(HOST, "tv", "CURRENT_APP"), json=load_fixture("current_app_hulu")
    )
    _register_action_endpoints(aioclient_mock, HOST, "tv")


@pytest.fixture(name="vizio_update_with_apps_on_input")
def vizio_update_with_apps_on_input_fixture(
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """TV with apps support but reporting an unknown app config."""
    aioclient_mock.get(url_for(HOST, "tv", "POWER_MODE"), json=load_fixture("power_on"))
    _register_common_endpoints(aioclient_mock, HOST, "tv")
    aioclient_mock.get(
        url_for(HOST, "tv", "INPUTS"), json=load_fixture("inputs_tv_with_cast")
    )
    aioclient_mock.get(
        url_for(HOST, "tv", "CURRENT_INPUT"), json=load_fixture("current_input_hdmi1")
    )
    aioclient_mock.get(
        settings_url(HOST, "tv", "audio"), json=load_fixture("audio_settings")
    )
    aioclient_mock.get(
        settings_options_url(HOST, "tv", "audio"), json=load_fixture("audio_options")
    )
    aioclient_mock.get(
        url_for(HOST, "tv", "CURRENT_APP"), json=load_fixture("current_app_unknown")
    )
    _register_action_endpoints(aioclient_mock, HOST, "tv")
