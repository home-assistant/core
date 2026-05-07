"""Test utilities for the vizio integration.

URL builders, fixture loading, mid-test override context managers, and
wire-level action assertions — anything test files (or conftest fixtures)
need to import. Conftest holds only pytest fixtures and their private
scaffolding.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
import json
from pathlib import Path
from typing import Any

from pyvizio.api._protocol import ENDPOINT, KEY_CODE

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Test setup helper.
# ---------------------------------------------------------------------------


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add config entry to hass and set up the integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# URL + fixture-loading utilities.
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> dict[str, Any]:
    """Load a device-state JSON fixture by name (without .json suffix)."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def url_for(host: str, device_class: str, key: str) -> str:
    """Return the full HTTPS URL pyvizio hits for an endpoint key."""
    return f"https://{host}{ENDPOINT[device_class][key]}"


def settings_url(host: str, device_class: str, suffix: str) -> str:
    """Return the URL for ``get_all_settings(suffix)``."""
    return f"{url_for(host, device_class, 'SETTINGS')}/{suffix}"


def settings_options_url(host: str, device_class: str, suffix: str) -> str:
    """Return the URL for ``get_setting_options(suffix, ...)``."""
    return f"{url_for(host, device_class, 'SETTINGS_OPTIONS')}/{suffix}"


# ---------------------------------------------------------------------------
# Override context managers — re-register a single endpoint at the front of
# the match queue, then remove it on exit so the prior response wins again.
# ---------------------------------------------------------------------------


def _prepend_mock(aioclient_mock: AiohttpClientMocker) -> Any:
    """Move the most-recently-added mock to the front of the match queue.

    ``AiohttpClientMocker`` matches first-registered first, and exposes no
    public ``prepend`` / ``replace`` API. Touching ``_mocks`` is the only
    way to make a later override take precedence over an existing mock.
    Adding a public method to ``AiohttpClientMocker`` upstream would let
    us drop this internal access.
    """
    new_mock = aioclient_mock._mocks.pop()
    aioclient_mock._mocks.insert(0, new_mock)
    return new_mock


@contextmanager
def override_power(
    aioclient_mock: AiohttpClientMocker,
    host: str,
    device_class: str,
    fixture: str,
) -> Iterator[None]:
    """Override POWER_MODE with the named fixture."""
    aioclient_mock.get(
        url_for(host, device_class, "POWER_MODE"), json=load_fixture(fixture)
    )
    new_mock = _prepend_mock(aioclient_mock)
    try:
        yield
    finally:
        aioclient_mock._mocks.remove(new_mock)


@contextmanager
def override_unavailable(
    aioclient_mock: AiohttpClientMocker, host: str, device_class: str
) -> Iterator[None]:
    """Make POWER_MODE return 500 (device unreachable)."""
    aioclient_mock.get(
        url_for(host, device_class, "POWER_MODE"),
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )
    new_mock = _prepend_mock(aioclient_mock)
    try:
        yield
    finally:
        aioclient_mock._mocks.remove(new_mock)


@contextmanager
def override_audio_settings(
    aioclient_mock: AiohttpClientMocker,
    host: str,
    device_class: str,
    fixture: str,
) -> Iterator[None]:
    """Override SETTINGS/audio with the named fixture."""
    aioclient_mock.get(
        settings_url(host, device_class, "audio"), json=load_fixture(fixture)
    )
    new_mock = _prepend_mock(aioclient_mock)
    try:
        yield
    finally:
        aioclient_mock._mocks.remove(new_mock)


@contextmanager
def override_audio_options(
    aioclient_mock: AiohttpClientMocker,
    host: str,
    device_class: str,
    fixture: str,
) -> Iterator[None]:
    """Override SETTINGS_OPTIONS/audio with the named fixture."""
    aioclient_mock.get(
        settings_options_url(host, device_class, "audio"),
        json=load_fixture(fixture),
    )
    new_mock = _prepend_mock(aioclient_mock)
    try:
        yield
    finally:
        aioclient_mock._mocks.remove(new_mock)


@contextmanager
def override_current_app(
    aioclient_mock: AiohttpClientMocker, host: str, fixture: str
) -> Iterator[None]:
    """Override CURRENT_APP (TV only) with the named fixture."""
    aioclient_mock.get(url_for(host, "tv", "CURRENT_APP"), json=load_fixture(fixture))
    new_mock = _prepend_mock(aioclient_mock)
    try:
        yield
    finally:
        aioclient_mock._mocks.remove(new_mock)


# ---------------------------------------------------------------------------
# Action assertions — inspect aioclient_mock.mock_calls to verify the
# integration sent the expected wire request.
# ---------------------------------------------------------------------------


def _put_calls(aioclient_mock: AiohttpClientMocker, *, url_contains: str) -> list:
    return [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "put" and url_contains in str(call[1])
    ]


def assert_key_press(
    aioclient_mock: AiohttpClientMocker,
    device_class: str,
    key_name: str,
    *,
    count: int = 1,
) -> None:
    """Assert ``count`` KEY_PRESS entries for ``key_name`` were sent.

    Pyvizio batches multiple key presses for the same key into a single PUT
    with one KEYLIST entry per press, so we count individual entries rather
    than HTTP requests.
    """
    codeset, code = KEY_CODE[device_class][key_name]
    matched = 0
    for call in _put_calls(aioclient_mock, url_contains="/key_command"):
        body = json.loads(call[2])
        for entry in body.get("KEYLIST") or ():
            if entry.get("CODESET") == codeset and entry.get("CODE") == code:
                matched += 1
    assert matched == count, (
        f"Expected {count} KEY_PRESS entries for {key_name} ({codeset},{code}), "
        f"found {matched}: "
        f"{[c[2] for c in _put_calls(aioclient_mock, url_contains='/key_command')]}"
    )


def assert_no_key_press(aioclient_mock: AiohttpClientMocker) -> None:
    """Assert no KEY_PRESS PUT was sent."""
    calls = _put_calls(aioclient_mock, url_contains="/key_command")
    assert not calls, f"Expected no KEY_PRESS, found: {[c[2] for c in calls]}"


def assert_no_launch_app(aioclient_mock: AiohttpClientMocker) -> None:
    """Assert no /app/launch PUT was sent."""
    calls = _put_calls(aioclient_mock, url_contains="/app/launch")
    assert not calls, f"Expected no launch_app, found: {[c[2] for c in calls]}"


def assert_set_input(aioclient_mock: AiohttpClientMocker, name: str) -> None:
    """Assert a PUT to CURRENT_INPUT with ``VALUE=name`` was sent."""
    matching = [
        call
        for call in _put_calls(aioclient_mock, url_contains="devices/current_input")
        if json.loads(call[2]).get("VALUE") == name
    ]
    assert len(matching) == 1, (
        f"Expected one set_input PUT with VALUE={name!r}, "
        f"found {len(matching)}: {[c[2] for c in matching]}"
    )


def assert_launch_app(
    aioclient_mock: AiohttpClientMocker,
    *,
    app_id: str,
    name_space: int,
    message: str | None = None,
) -> None:
    """Assert a PUT to /app/launch with the expected app config was sent."""
    matching = []
    for call in _put_calls(aioclient_mock, url_contains="/app/launch"):
        body = json.loads(call[2])
        value = body.get("VALUE", body)
        if (
            value.get("APP_ID") == app_id
            and value.get("NAME_SPACE") == name_space
            and value.get("MESSAGE") == message
        ):
            matching.append(call)
    assert len(matching) == 1, (
        f"Expected one launch_app PUT with APP_ID={app_id!r} NAME_SPACE={name_space} "
        f"MESSAGE={message!r}, found {len(matching)}: "
        f"{[c[2] for c in _put_calls(aioclient_mock, url_contains='/app/launch')]}"
    )


def assert_set_setting(
    aioclient_mock: AiohttpClientMocker, *, name: str, value: Any
) -> None:
    """Assert a PUT to a settings endpoint matching ``name`` with ``VALUE=value``."""
    matching = []
    for call in _put_calls(aioclient_mock, url_contains=f"/{name}"):
        body = json.loads(call[2])
        if body.get("VALUE") == value:
            matching.append(call)
    assert len(matching) == 1, (
        f"Expected one set_setting PUT for {name}={value!r}, "
        f"found {len(matching)}: {[c[2] for c in matching]}"
    )
