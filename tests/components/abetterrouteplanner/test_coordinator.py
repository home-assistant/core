"""Tests for the garage polling coordinator (``AbrpVehiclesCoordinator``).

The telemetry coordinator is a thin push coordinator whose HA-side policy is
covered in ``test_telemetry_state.py``; all wire parsing / merge / monotonicity
/ reconnect machinery now lives in :mod:`aioabrp` and is tested there. What
remains here is the garage coordinator: it polls the authenticated user's
vehicles, fetches the v2 catalog (self-healing: retried every poll until the
first success, and re-fetched once when a new/unmatched vehicle model appears),
and joins each raw vehicle into a :class:`GarageVehicle` carrying composed
device-card fields.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from aioabrp import AbrpApiError, AbrpAuthError, AbrpVehicle
import pytest

from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpVehiclesCoordinator,
    GarageVehicle,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_MODEL_2,
    build_catalog_entry,
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


# ---------- catalog self-healing (retry-until-loaded + refetch on new model) -


async def test_catalog_not_refetched_once_loaded(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """Once loaded, a poll with no new typecode does not re-fetch the catalog.

    The ~850 KB catalog must not be re-hit on every 10-min poll. After the
    first success, every typecode in the garage is recorded as evaluated, so a
    steady-state poll (even one whose vehicle the catalog can't match) does not
    re-fetch. A regression would surface as ``call_count == 2``.
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
async def test_catalog_fetch_failure_degrades_this_poll(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    catalog_error: Exception,
) -> None:
    """Catalog-fetch failure is non-fatal for the poll and NOT marked loaded.

    Auth / api / timeout on the catalog endpoint degrade to the (empty) catalog
    for THIS poll — the refresh still ships the garage with device models
    falling back to the raw typecode — and a warning is logged. Crucially the
    catalog is not marked loaded, so the next poll retries (see
    :func:`test_catalog_retried_until_first_success`). The garage 401 path
    (separate) still triggers reauth; the catalog 401 is fail-soft because the
    catalog endpoint can fail independently of the per-user garage endpoint.
    """
    with patch(
        "aioabrp.AbrpClient.async_get_catalog",
        new_callable=AsyncMock,
        side_effect=catalog_error,
    ):
        await garage_coordinator.async_refresh()

    assert garage_coordinator.last_update_success
    assert len(garage_coordinator.data) == 2
    assert garage_coordinator.data[0].device_model is None
    # Not marked loaded → the next poll retries (self-healing, not give-up).
    assert garage_coordinator._catalog == {}
    assert garage_coordinator._catalog_loaded is False
    assert any("catalog" in record.message.lower() for record in caplog.records)


async def test_catalog_retried_until_first_success(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """A failing catalog fetch is retried every poll until it succeeds.

    Replaces the old give-up-for-the-session behaviour: a transient catalog
    failure (or an ABRP feature-plan entitlement that lags first setup) must
    not strand device models on the raw typecode until a manual reload. After
    the success the catalog is reused (no further re-fetch).
    """
    catalog = {MOCK_VEHICLE_MODEL: build_catalog_entry()}
    with patch(
        "aioabrp.AbrpClient.async_get_catalog",
        new_callable=AsyncMock,
        side_effect=[AbrpApiError("HTTP 403"), AbrpApiError("HTTP 403"), catalog],
    ) as mock_catalog:
        await garage_coordinator.async_refresh()  # fail 1
        assert garage_coordinator.data[0].device_model is None
        assert garage_coordinator._catalog_loaded is False

        await garage_coordinator.async_refresh()  # fail 2
        assert mock_catalog.call_count == 2
        assert garage_coordinator.data[0].device_model is None

        await garage_coordinator.async_refresh()  # success
        assert mock_catalog.call_count == 3
        assert garage_coordinator._catalog_loaded is True
        assert garage_coordinator.data[0].device_model is not None

        # No further re-fetch once loaded (a 4th call would raise StopIteration
        # against the 3-item side_effect, so this also pins "no refetch").
        await garage_coordinator.async_refresh()
        assert mock_catalog.call_count == 3


async def test_new_unmatched_typecode_triggers_one_refetch(
    garage_coordinator: AbrpVehiclesCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """A newly-appearing vehicle model re-fetches the catalog exactly once.

    A model added to ABRP's catalog after the initial load is picked up
    without a config-entry reload; but once a fresh catalog has been evaluated
    against a typecode, that typecode never re-fetches again (so a genuinely-
    absent model can't trigger an ~850 KB fetch on every poll).
    """
    veh_a = AbrpVehicle(
        vehicle_id=MOCK_VEHICLE_ID,
        name="A",
        vehicle_model=MOCK_VEHICLE_MODEL,
        paint=None,
    )
    veh_b = AbrpVehicle(
        vehicle_id=MOCK_VEHICLE_ID_2,
        name="B",
        vehicle_model=MOCK_VEHICLE_MODEL_2,
        paint=None,
    )
    cat_a = {MOCK_VEHICLE_MODEL: build_catalog_entry()}
    cat_ab = {
        MOCK_VEHICLE_MODEL: build_catalog_entry(),
        MOCK_VEHICLE_MODEL_2: build_catalog_entry(
            typecode=MOCK_VEHICLE_MODEL_2, manufacturer="Rivian", model="R1S"
        ),
    }
    with patch(
        "aioabrp.AbrpClient.async_get_catalog",
        new_callable=AsyncMock,
        side_effect=[cat_a, cat_ab],
    ) as mock_catalog:
        # Poll 1: only A present → first load (call 1); A resolves.
        mock_abrp_client.return_value = [veh_a]
        await garage_coordinator.async_refresh()
        assert mock_catalog.call_count == 1
        assert garage_coordinator.data[0].device_model is not None

        # Poll 2: new B appears, unmatched by cat_a → one refetch (call 2);
        # cat_ab now resolves B.
        mock_abrp_client.return_value = [veh_a, veh_b]
        await garage_coordinator.async_refresh()
        assert mock_catalog.call_count == 2
        veh_b_carrier = next(
            v for v in garage_coordinator.data if v.vehicle_id == MOCK_VEHICLE_ID_2
        )
        assert veh_b_carrier.device_model is not None

        # Poll 3: same A + B, both already evaluated → no further refetch.
        await garage_coordinator.async_refresh()
        assert mock_catalog.call_count == 2


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
