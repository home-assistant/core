"""Tests for the one-shot garage fetch (``async_fetch_garage``).

The telemetry coordinator is a thin push coordinator whose HA-side policy is
covered in ``test_telemetry_state.py``; all wire parsing / merge / monotonicity
/ reconnect machinery now lives in :mod:`aioabrp` and is tested there. What
remains here is :func:`async_fetch_garage`: the setup-time fetch of the
authenticated user's vehicles that resolves each vehicle's device-card display
per typecode (degrading per-vehicle on failure) and pairs each raw vehicle with
its :class:`aioabrp.VehicleModelDisplay` (or ``None`` on a miss).
"""

import logging
from unittest.mock import AsyncMock, patch

from aioabrp import AbrpApiError, AbrpAuthError, AbrpClient, StaticAuth
import pytest

from homeassistant.components.abetterrouteplanner.const import ABRP_APP_KEY
from homeassistant.components.abetterrouteplanner.coordinator import async_fetch_garage
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_MODEL_2,
    build_vehicle_model_display,
)


@pytest.fixture(name="client")
async def client_fixture(hass: HomeAssistant) -> AbrpClient:
    """An ``AbrpClient`` whose methods are patched by ``mock_abrp_client``.

    Async so the aiohttp client session is grabbed inside a running event loop.
    The class-level patches in ``mock_abrp_client`` cover this instance, so the
    static auth here is never exercised against a real endpoint.
    """
    return AbrpClient(
        async_get_clientsession(hass), ABRP_APP_KEY, StaticAuth("test-tok")
    )


async def test_fetch_pairs_vehicles_with_display(
    client: AbrpClient,
    mock_abrp_client: AsyncMock,
) -> None:
    """A fetch returns each raw vehicle paired with its display.

    ``mock_abrp_client`` returns the 2-vehicle fixture garage; with no display
    fixtures the default mock 404s every typecode, so each pair carries the raw
    identity fields with a ``None`` display (the raw-typecode fallback happens
    later at the DeviceInfo layer).
    """
    paired = await async_fetch_garage(client)

    assert len(paired) == 2
    (raw0, display0), (raw1, display1) = paired
    assert raw0.vehicle_id == MOCK_VEHICLE_ID
    assert raw0.vehicle_model == MOCK_VEHICLE_MODEL
    assert raw1.vehicle_id == MOCK_VEHICLE_ID_2
    # Empty catalog → display is None for every vehicle.
    assert display0 is None
    assert display1 is None


async def test_display_fetched_for_every_vehicle(
    client: AbrpClient,
    mock_abrp_client: AsyncMock,
) -> None:
    """The display endpoint is hit once per vehicle on a fetch."""
    with patch(
        "aioabrp.AbrpClient.async_get_vehicle_model_display",
        return_value=build_vehicle_model_display(),
    ) as mock_display:
        await async_fetch_garage(client)
        assert mock_display.call_count == 2


@pytest.mark.parametrize(
    "display_error",
    [
        pytest.param(AbrpAuthError("HTTP 401"), id="auth_error"),
        pytest.param(AbrpApiError("HTTP 404"), id="api_error"),
        pytest.param(TimeoutError("budget exceeded"), id="timeout_error"),
    ],
)
async def test_display_failure_degrades_only_that_vehicle(
    client: AbrpClient,
    mock_abrp_client: AsyncMock,
    display_error: Exception,
) -> None:
    """A per-vehicle display failure falls that vehicle back; the fetch succeeds.

    The first vehicle's display fails (auth / api / timeout) → its display is
    ``None`` (raw-typecode fallback); the second vehicle still enriches. An
    ``AbrpAuthError`` here does NOT raise ``ConfigEntryAuthFailed`` — only the
    garage-list call's auth error does (covered separately).
    """
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = display_error
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL_2] = (
        build_vehicle_model_display(manufacturer="Rivian", model="R1S")
    )

    paired = await async_fetch_garage(client)

    by_id = {raw.vehicle_id: display for raw, display in paired}
    assert by_id[MOCK_VEHICLE_ID] is None
    assert by_id[MOCK_VEHICLE_ID_2] is not None
    assert by_id[MOCK_VEHICLE_ID_2].manufacturer == "Rivian"


async def test_unexpected_display_error_degrades_and_warns(
    client: AbrpClient,
    mock_abrp_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unexpected (non-aioabrp) display error degrades the vehicle and WARNs.

    Unlike the expected auth / api / timeout failures (logged at DEBUG), an
    unforeseen ``Exception`` is logged at WARNING so it surfaces. The vehicle
    still falls back (display ``None``) and the whole fetch still succeeds.
    """
    caplog.set_level(logging.WARNING)
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = ValueError("boom")

    paired = await async_fetch_garage(client)

    by_id = {raw.vehicle_id: display for raw, display in paired}
    assert by_id[MOCK_VEHICLE_ID] is None
    assert any(
        record.levelno == logging.WARNING and "display" in record.message.lower()
        for record in caplog.records
    )


async def test_garage_auth_error_raises_config_entry_auth_failed(
    client: AbrpClient,
    mock_abrp_client: AsyncMock,
) -> None:
    """An ``AbrpAuthError`` from the garage fetch maps to ``ConfigEntryAuthFailed``.

    A revoked/rotated refresh token surfaces from the auth wrapper as
    ``AbrpAuthError``; the fetch converts it so setup fails into ``SETUP_ERROR``
    (reauth-eligible) rather than retrying.
    """
    mock_abrp_client.side_effect = AbrpAuthError("invalid session")

    with pytest.raises(ConfigEntryAuthFailed):
        await async_fetch_garage(client)


async def test_garage_api_error_raises_config_entry_not_ready(
    client: AbrpClient,
    mock_abrp_client: AsyncMock,
) -> None:
    """An ``AbrpApiError`` from the garage fetch maps to ``ConfigEntryNotReady``.

    A transient backend failure maps to a retry rather than an auth-error state.
    """
    mock_abrp_client.side_effect = AbrpApiError("backend overloaded")

    with pytest.raises(ConfigEntryNotReady):
        await async_fetch_garage(client)
