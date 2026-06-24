"""Tests for the garage polling coordinator (``AbrpVehiclesCoordinator``).

The telemetry coordinator is a thin push coordinator whose HA-side policy is
covered in ``test_telemetry_state.py``; all wire parsing / merge / monotonicity
/ reconnect machinery now lives in :mod:`aioabrp` and is tested there. What
remains here is the garage coordinator: it polls the authenticated user's
vehicles, resolves each vehicle's device-card strings via the per-typecode
display endpoint (degrading per-vehicle on failure), and joins each raw
vehicle into a :class:`GarageVehicle` carrying composed device-card fields.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aioabrp import AbrpApiError, AbrpAuthError
import pytest

from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpVehiclesCoordinator,
    GarageVehicle,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_MODEL_2,
    build_vehicle_model_display,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="oauth_session")
def oauth_session_fixture() -> MagicMock:
    """A ``MagicMock(spec=OAuth2Session)`` with a quiet token-refresh path.

    ``async_ensure_token_valid`` is an ``AsyncMock`` returning ``None`` so the
    auth wrapper's pre-request refresh succeeds without real HTTP, and
    ``token`` exposes a synthetic access token.
    """
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"access_token": "test-tok"}
    return session


@pytest.fixture(name="garage_coordinator")
async def garage_coordinator_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    oauth_session: MagicMock,
) -> AbrpVehiclesCoordinator:
    """A garage coordinator bound to a real (added) config entry.

    Async so the ``AbrpClient`` (which grabs the aiohttp client session) is
    built inside a running event loop.
    """
    config_entry.add_to_hass(hass)
    return AbrpVehiclesCoordinator(hass, config_entry, oauth_session)


# ---------- vehicle fetch → GarageVehicle list -----------------------------


async def test_refresh_builds_garage_vehicle_list(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """A refresh fetches the garage and joins each raw vehicle into a carrier.

    ``mock_abrp_client`` returns the 2-vehicle fixture garage; with no display
    fixtures the default mock 404s every typecode, so each result is a
    :class:`GarageVehicle` re-exporting the raw identity fields with composed
    device fields left ``None`` (the raw-typecode fallback happens later at
    the DeviceInfo layer).
    """
    await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    vehicles = garage_coordinator.data
    assert len(vehicles) == 2
    assert all(isinstance(item, GarageVehicle) for item in vehicles)

    first = vehicles[0]
    assert first.vehicle_id == MOCK_VEHICLE_ID
    assert first.vehicle_model == MOCK_VEHICLE_MODEL
    # Empty catalog → composed device fields are None (DeviceInfo layer
    # falls back to the raw typecode, not the coordinator).
    assert first.device_model is None
    assert first.device_manufacturer is None


# ---------- display endpoint enrichment ------------------------------------


async def test_refresh_enriches_device_fields_from_display(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """A display hit composes ``device_model`` / ``device_manufacturer``.

    With a display fixture for the typecode, the composed manufacturer/model
    surface on the carrier rather than the raw-typecode fallback.
    """
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = (
        build_vehicle_model_display()
    )

    await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    first = garage_coordinator.data[0]
    assert first.device_manufacturer == "Rivian"
    # Composed per ``_compose_device_model``: "{mfr} {model}" + " {year}" +
    # " {title}".
    assert first.device_model == "Rivian R2 2026 Standard Long Range RWD"


# ---------- per-vehicle display fetch (no cache) ---------------------------


async def test_display_fetched_for_every_vehicle_each_poll(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """The display endpoint is hit once per vehicle on every poll (no cache).

    Two vehicles in the fixture garage → two display calls per refresh; a
    second refresh hits the endpoint again (the value is intentionally not
    cached across polls).
    """
    with patch(
        "aioabrp.AbrpClient.async_get_vehicle_model_display",
        return_value=build_vehicle_model_display(),
    ) as mock_display:
        await garage_coordinator.async_refresh()
        assert mock_display.call_count == 2

        await garage_coordinator.async_refresh()
        assert mock_display.call_count == 4


@pytest.mark.parametrize(
    "display_error",
    [
        pytest.param(AbrpAuthError("HTTP 401"), id="auth_error"),
        pytest.param(AbrpApiError("HTTP 404"), id="api_error"),
        pytest.param(TimeoutError("budget exceeded"), id="timeout_error"),
    ],
)
async def test_display_failure_degrades_only_that_vehicle(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
    display_error: Exception,
) -> None:
    """A per-vehicle display failure falls that vehicle back, refresh succeeds.

    The first vehicle's display fails (auth / api / timeout) → its device
    fields stay ``None`` (raw-typecode fallback); the second vehicle still
    enriches. The whole refresh still succeeds — only the garage call's auth /
    api error fails a refresh (covered separately). An ``AbrpAuthError`` here
    does NOT raise ``ConfigEntryAuthFailed`` from this path.
    """
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = display_error
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL_2] = (
        build_vehicle_model_display(manufacturer="Rivian", model="R1S")
    )

    await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    by_id = {v.vehicle_id: v for v in garage_coordinator.data}
    assert by_id[MOCK_VEHICLE_ID].device_model is None
    assert by_id[MOCK_VEHICLE_ID].device_manufacturer is None
    assert by_id[MOCK_VEHICLE_ID_2].device_manufacturer == "Rivian"


async def test_unexpected_display_error_degrades_and_warns(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unexpected (non-aioabrp) display error degrades the vehicle and WARNs.

    Unlike the expected auth / api / timeout failures (logged at DEBUG), an
    unforeseen ``Exception`` is logged at WARNING so it surfaces. The vehicle
    still falls back to the raw-typecode (device fields ``None``) and the whole
    refresh still succeeds — an unexpected per-vehicle failure must never fail
    the poll.
    """
    caplog.set_level(logging.WARNING)
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = ValueError("boom")

    await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    by_id = {v.vehicle_id: v for v in garage_coordinator.data}
    assert by_id[MOCK_VEHICLE_ID].device_model is None
    assert by_id[MOCK_VEHICLE_ID].device_manufacturer is None
    assert any(
        record.levelno == logging.WARNING and "display" in record.message.lower()
        for record in caplog.records
    )


# ---------- garage error mapping -------------------------------------------


async def _setup_failure(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Register the OAuth implementation and attempt setup, expecting failure.

    Drives the public config-entry setup path so the garage coordinator's
    first refresh runs and its error mapping is observed via ``entry.state``.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_garage_auth_error_fails_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """An ``AbrpAuthError`` from the garage fetch puts the entry in ``SETUP_ERROR``.

    A revoked/rotated refresh token surfaces from the auth wrapper as
    ``AbrpAuthError``; the coordinator converts it to ``ConfigEntryAuthFailed``
    so setup fails into ``SETUP_ERROR`` (reauth-eligible) rather than retrying.
    """
    mock_abrp_client.side_effect = AbrpAuthError("invalid session")

    await _setup_failure(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_garage_api_error_retries_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_abrp_client: AsyncMock,
) -> None:
    """An ``AbrpApiError`` from the garage fetch puts the entry in ``SETUP_RETRY``.

    A transient backend failure maps to ``ConfigEntryNotReady``, so HA schedules
    a retry rather than treating it as an auth problem.
    """
    mock_abrp_client.side_effect = AbrpApiError("backend overloaded")

    await _setup_failure(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


# ---------- GarageVehicle value-equality (poll-notify suppression) ---------


async def test_garage_vehicle_value_equality_suppresses_listener_fires(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """Two refreshes over an unchanged garage produce value-equal carriers.

    ``TimestampDataUpdateCoordinator`` compares ``previous_data == self.data``
    to decide whether to re-fire listeners. Without value-equality on
    ``GarageVehicle`` (a ``__slots__`` class) the comparison would fall back to
    identity and spuriously re-fire stale-device / auto-add / rename listeners
    on every 10-min poll. Two refreshes over an unchanged garage must yield
    element-wise-equal carriers that are nonetheless distinct objects.
    """
    await garage_coordinator.async_refresh()
    first = garage_coordinator.data
    await garage_coordinator.async_refresh()
    second = garage_coordinator.data

    assert first == second
    # Distinct object identities — equality is by value, not identity.
    assert first[0] is not second[0]
    assert hash(first[0]) == hash(second[0])
