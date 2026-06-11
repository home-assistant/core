"""Tests for the garage polling coordinator (``AbrpVehiclesCoordinator``).

The telemetry coordinator is a thin push coordinator whose HA-side policy is
covered in ``test_telemetry_state.py``; all wire parsing / merge / monotonicity
/ reconnect machinery now lives in :mod:`aioabrp` and is tested there. What
remains here is the garage coordinator: it polls the authenticated user's
vehicles, lazily fetches the v2 catalog once, and joins each raw vehicle into a
:class:`GarageVehicle` carrying composed device-card fields.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from aioabrp import AbrpApiError, AbrpAuthError
import pytest

from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpVehiclesCoordinator,
    GarageVehicle,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MOCK_VEHICLE_ID, MOCK_VEHICLE_MODEL, build_catalog_entry

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

    ``mock_abrp_client`` returns the 2-vehicle fixture garage with an empty
    catalog; each result is a :class:`GarageVehicle` re-exporting the raw
    identity fields. On a catalog miss the composed device fields stay ``None``
    (the raw-typecode fallback happens later at the DeviceInfo layer).
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


# ---------- catalog enrichment (compose_device_info join) ------------------


async def test_refresh_enriches_device_fields_from_catalog(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """A catalog hit composes ``device_model`` / ``device_manufacturer``.

    With the typecode present in the catalog, the join surfaces the catalog's
    manufacturer/model on the carrier rather than the raw typecode fallback.
    """
    with patch(
        "aioabrp.AbrpClient.async_get_catalog",
        new_callable=AsyncMock,
        return_value={MOCK_VEHICLE_MODEL: build_catalog_entry()},
    ):
        await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    first = garage_coordinator.data[0]
    assert first.device_manufacturer == "Rivian"
    # Composed per ``_compose_device_model``: "{mfr} {model}" + " {year}" +
    # " {title}".
    assert first.device_model == (
        "Rivian R2 2026 Rivian R2 2027 Standard Long Range RWD"
    )


# ---------- catalog lazy-once cache ----------------------------------------


async def test_catalog_fetched_once_then_reused(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """The catalog is fetched on the first refresh and never re-fetched.

    Lazy-once invariant: reload is the only refresh path; mid-session ABRP
    catalog changes don't materialise until reload. A regression that
    refetched every poll would surface as ``call_count == 2``.
    """
    with patch(
        "aioabrp.AbrpClient.async_get_catalog",
        new_callable=AsyncMock,
        return_value={MOCK_VEHICLE_MODEL: build_catalog_entry()},
    ) as mock_catalog:
        await garage_coordinator.async_refresh()
        assert mock_catalog.call_count == 1

        await garage_coordinator.async_refresh()
        assert mock_catalog.call_count == 1


@pytest.mark.parametrize(
    "catalog_error",
    [
        pytest.param(AbrpAuthError("HTTP 401"), id="auth_error"),
        pytest.param(AbrpApiError("HTTP 500"), id="api_error"),
        pytest.param(TimeoutError("budget exceeded"), id="timeout_error"),
    ],
)
async def test_catalog_fetch_failure_degrades_to_empty(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    catalog_error: Exception,
) -> None:
    """Catalog-fetch failure is non-fatal — the garage still ships.

    Auth / api / timeout on the catalog endpoint degrade to an empty catalog:
    the refresh returns the garage (device_model falls back to the raw
    typecode), the cache is set to ``{}`` so the lazy-once gate doesn't retry
    until reload, and a warning is logged. The garage 401 path (separate) still
    triggers reauth; the catalog 401 is fail-soft because the catalog endpoint
    may rate-limit independently of the per-user garage endpoint.
    """
    with patch(
        "aioabrp.AbrpClient.async_get_catalog",
        new_callable=AsyncMock,
        side_effect=catalog_error,
    ):
        await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    assert len(garage_coordinator.data) == 2
    # Cache is initialised to {} so subsequent polls don't retry until reload.
    assert garage_coordinator._catalog == {}
    assert any("catalog" in record.message.lower() for record in caplog.records)


# ---------- garage error mapping -------------------------------------------


async def test_garage_auth_error_raises_config_entry_auth_failed(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """An ``AbrpAuthError`` from the garage fetch maps to ``ConfigEntryAuthFailed``.

    A revoked/rotated refresh token surfaces from the auth wrapper as
    ``AbrpAuthError``; the coordinator converts it so HA starts reauth.
    """
    mock_abrp_client.side_effect = AbrpAuthError("invalid session")

    with pytest.raises(ConfigEntryAuthFailed):
        await garage_coordinator._async_update_data()


async def test_garage_api_error_raises_update_failed(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """An ``AbrpApiError`` from the garage fetch maps to ``UpdateFailed``."""
    mock_abrp_client.side_effect = AbrpApiError("backend overloaded")

    with pytest.raises(UpdateFailed):
        await garage_coordinator._async_update_data()


# ---------- GarageVehicle value-equality (poll-notify suppression) ---------


async def test_garage_vehicle_value_equality_suppresses_listener_fires(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """Two refreshes over an unchanged garage produce value-equal carriers.

    ``TimestampDataUpdateCoordinator`` suppresses listener fires when a poll
    returns ``previous_data == self.data``. Without value-equality on
    ``GarageVehicle`` (a ``__slots__`` class) the comparison would fall back to
    identity and spuriously re-fire stale-device / auto-add / rename listeners
    on every 10-min poll. The two polls must compare equal element-wise.
    """
    first = await garage_coordinator._async_update_data()
    second = await garage_coordinator._async_update_data()

    assert first == second
    # Distinct object identities — equality is by value, not identity.
    assert first[0] is not second[0]
    assert hash(first[0]) == hash(second[0])
