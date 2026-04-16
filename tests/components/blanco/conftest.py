"""Common fixtures and helpers for the blanco tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.blanco.const import (
    CONF_APP_ID,
    CONF_APP_LOCALE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_TOKEN,
    CONF_TOKEN_TYPE,
)
from homeassistant.components.blanco.coordinator import BlancoDataUpdateCoordinator
from homeassistant.components.blanco.definitions import BlancoDeviceType

# ── Shared test constants ──────────────────────────────────────────────────────

TEST_DEV_ID = "abc123devid"
"""Device ID used in all coordinator and entity tests."""
TEST_SERIAL = "SN123456"
"""Serial number used in all coordinator and entity tests."""
TEST_TOKEN = "test-bearer-token"
"""Bearer token used in all coordinator and entity tests."""
TEST_APP_ID = "test-app-id"
"""App registration ID used in all coordinator and entity tests."""


# ── Pytest fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry so config-flow tests do not start a real coordinator."""
    with patch(
        "homeassistant.components.blanco.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a minimal HomeAssistant-like mock sufficient for coordinator tests."""
    hass = MagicMock()
    hass.config.components = set()
    hass.config_entries.async_update_entry = MagicMock()
    hass.config.time_zone = "UTC"
    return hass


# ── Non-fixture helpers ────────────────────────────────────────────────────────


def make_mock_entry(data: dict | None = None) -> MagicMock:
    """Return a MagicMock configured to behave like a ConfigEntry.

    The default data dict contains all keys needed by BlancoDataUpdateCoordinator.
    """
    default_data: dict = {
        CONF_TOKEN: TEST_TOKEN,
        CONF_TOKEN_TYPE: "Bearer",
        CONF_DEV_ID: TEST_DEV_ID,
        CONF_APP_ID: TEST_APP_ID,
        CONF_SERIAL: TEST_SERIAL,
        CONF_APP_LOCALE: "en",
        CONF_DEV_TYPE: BlancoDeviceType.AIO,
    }
    entry = MagicMock()
    entry.data = {**default_data, **(data or {})}
    entry.title = TEST_SERIAL
    return entry


def make_coordinator(
    hass: MagicMock,
    entry: MagicMock | None = None,
    dev_type: BlancoDeviceType = BlancoDeviceType.AIO,
    session: MagicMock | None = None,
) -> BlancoDataUpdateCoordinator:
    """Create a BlancoDataUpdateCoordinator for use in unit tests.

    Uses *entry* if provided, otherwise creates one via make_mock_entry() with
    the given *dev_type* stored in its data.

    The *session* parameter controls the aiohttp session injected into the
    underlying BlancoApiClient.  When omitted a plain MagicMock() is used,
    which is sufficient for tests that do not exercise HTTP calls.
    """
    if entry is None:
        entry = make_mock_entry(data={CONF_DEV_TYPE: int(dev_type)})
    if session is None:
        mock_session = MagicMock()
    else:
        mock_session = session
    with (
        patch(
            # Patch at the usage site (coordinator imports the function directly).
            "homeassistant.components.blanco.coordinator.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            # Newer HA versions call frame.report_usage() in DataUpdateCoordinator.__init__
            # which requires the HA event loop to be running.  Suppress it in unit tests.
            "homeassistant.helpers.frame.report_usage",
        ),
    ):
        return BlancoDataUpdateCoordinator(
            hass=hass,
            entry=entry,
            token=TEST_TOKEN,
            token_type="Bearer",
            dev_id=TEST_DEV_ID,
            dev_type=int(dev_type),
            serial=TEST_SERIAL,
            app_id=TEST_APP_ID,
        )


def make_get_response(status: int = 200, json_data: dict | None = None) -> MagicMock:
    """Return an async context-manager mock that simulates an aiohttp GET response.

    Args:
        status: HTTP status code the mock response will report.
        json_data: Parsed JSON body the mock response will return from .json().
    """
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data or {})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm
