"""Tests for device-metadata propagation to the HA device registry.

The listener is registered via ``entry.async_on_unload(
garage_coordinator.async_add_listener(_propagate_device_metadata))`` after the
first garage refresh. It iterates ``coordinator.data``, looks up each
vehicle's device via ``dr.async_get_device(identifiers={(DOMAIN, scope)})``,
and reconciles three fields against the anchor formula: ``name``
(``vehicle.name or vehicle.vehicle_model``), plus the integration-owned
``model``
(``vehicle.device_model or vehicle.vehicle_model``) and ``manufacturer``
(``vehicle.device_manufacturer``, left unset when the make can't be
resolved). Each field is written only when it differs, so an unchanged poll
is a no-op.

Changes are driven entirely through the garage coordinator: each test
reassigns ``mock_abrp_client.return_value`` (the patched
``AbrpClient.async_get_vehicles``) to a fresh ``list[AbrpVehicle]``, then
triggers ``garage_coordinator.async_refresh()`` to fire the listener. The
``fake_stream`` fixture collapses the setup pre-warm sleep to 0, so setup
returns immediately without a real SSE consumer and these tests need neither
``freezer`` nor any ``asyncio.sleep`` patching.
"""

from typing import Any
from unittest.mock import AsyncMock

from aioabrp import AbrpVehicle
import pytest

from homeassistant.components.abetterrouteplanner import AbrpData
from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    MOCK_VEHICLE_MODEL,
    SENSOR_TEST_SUB,
    build_vehicle_model_display,
)

from tests.common import MockConfigEntry

# Two synthetic vehicle-model strings for "vehicle_model changes" test cases.
_VEHICLE_MODEL_V1 = "mg:4:22:std:fwd:w21"
_VEHICLE_MODEL_V2 = "mg:4:22:std:fwd:w22"


async def _setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Register the integration's OAuth implementation and set up the entry.

    The ``fake_stream`` fixture patches both ``TelemetryStream`` (with a
    synchronous double) and ``PREWARM_WINDOW_SECONDS`` to ``0``, so setup
    returns immediately without a real SSE consumer or wall-clock wait.
    """
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _poll(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Trigger one garage-coordinator refresh and drain the event bus.

    Directly calls ``async_refresh()`` on the coordinator so the
    ``_propagate_device_metadata`` listener fires against whatever
    ``mock_abrp_client.return_value`` is currently set to.
    """
    runtime_data: AbrpData = entry.runtime_data
    await runtime_data.garage_coordinator.async_refresh()
    await hass.async_block_till_done()


def _make_vehicle(
    vehicle_id: int = MOCK_VEHICLE_ID,
    name: str | None = None,
    vehicle_model: str = MOCK_VEHICLE_MODEL,
) -> AbrpVehicle:
    """Build a minimal ``AbrpVehicle`` with controlled name for rename tests."""
    return AbrpVehicle(
        vehicle_id=vehicle_id, name=name, vehicle_model=vehicle_model, paint=None
    )


def _device_scope(entry: MockConfigEntry, vehicle_id: int) -> str:
    """Return the device-identifier scope string for a given vehicle."""
    return f"{entry.unique_id}_{vehicle_id}"


# ---------------------------------------------------------------------------
# Tests 1, 3, 4, 5 — parametrize table
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
@pytest.mark.parametrize(
    (
        "poll1_name",
        "poll1_vehicle_model",
        "poll2_name",
        "poll2_vehicle_model",
        "expected_name",
    ),
    [
        pytest.param(
            "MG4",
            _VEHICLE_MODEL_V1,
            "Sofie's MG4",
            _VEHICLE_MODEL_V1,
            "Sofie's MG4",
            id="rename_propagates",
        ),
        pytest.param(
            "MG4",
            _VEHICLE_MODEL_V1,
            "MG4",
            _VEHICLE_MODEL_V1,
            "MG4",
            id="no_op_unchanged",
        ),
        pytest.param(
            None,
            _VEHICLE_MODEL_V1,
            None,
            _VEHICLE_MODEL_V2,
            _VEHICLE_MODEL_V2,
            id="fallback_vehicle_model_changes",
        ),
        pytest.param(
            None,
            _VEHICLE_MODEL_V1,
            "Custom",
            _VEHICLE_MODEL_V1,
            "Custom",
            id="null_to_custom_string",
        ),
        pytest.param(
            "Foo",
            _VEHICLE_MODEL_V1,
            None,
            _VEHICLE_MODEL_V1,
            _VEHICLE_MODEL_V1,
            id="custom_string_to_null_fallback",
        ),
    ],
)
async def test_rename_propagation_table(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    poll1_name: str | None,
    poll1_vehicle_model: str,
    poll2_name: str | None,
    poll2_vehicle_model: str,
    expected_name: str,
) -> None:
    """Rename listener propagates (or correctly skips) vehicle name changes.

    Sequence:
    1. Poll 1: vehicle with ``poll1_name``/``poll1_vehicle_model`` → device registered.
    2. Poll 2: vehicle data updated to ``poll2_name``/``poll2_vehicle_model``.
    3. Assert ``device.name == expected_name``.

    Cases ``rename_propagates``, ``fallback_vehicle_model_changes``,
    ``null_to_custom_string``, ``custom_string_to_null_fallback`` exercise the
    listener pushing ``vehicle.name or vehicle.vehicle_model`` into the device
    registry; ``no_op_unchanged`` exercises the unchanged-name short-circuit.
    """
    mock_abrp_client.return_value = [
        _make_vehicle(MOCK_VEHICLE_ID, poll1_name, poll1_vehicle_model)
    ]
    await _setup_integration(hass, config_entry_with_vehicles)

    scope = _device_scope(config_entry_with_vehicles, MOCK_VEHICLE_ID)
    device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
    assert device is not None
    assert device.name == (poll1_name or poll1_vehicle_model)

    # Trigger poll 2: vehicle renamed/remodelled in ABRP
    mock_abrp_client.return_value = [
        _make_vehicle(MOCK_VEHICLE_ID, poll2_name, poll2_vehicle_model)
    ]
    await _poll(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
    assert device is not None
    assert device.name == expected_name


# ---------------------------------------------------------------------------
# New vehicle mid-life robustness
# ---------------------------------------------------------------------------

_NEW_VEHICLE_ID = 999_000_001


@pytest.mark.usefixtures("fake_stream")
async def test_new_vehicle_mid_life_does_not_crash(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A new vehicle appearing in a poll must not crash the rename listener.

    The rename listener calls ``dr.async_get_device`` for every vehicle in
    ``coordinator.data``.  A vehicle that's not currently selected returns
    ``None`` from ``async_get_device`` (no device has ever been registered
    for it); the listener must guard with ``if device is None: continue``.

    Asserts:
    - Entry remains LOADED (no exception in listener).
    - No device is created for the new vehicle (it's not in ``VEHICLE_IDS``).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID)],
        },
    )
    mock_abrp_client.return_value = [
        _make_vehicle(MOCK_VEHICLE_ID, "MG4", _VEHICLE_MODEL_V1)
    ]
    await _setup_integration(hass, entry)

    # Poll 2: a brand-new vehicle appears that was never in CONF_VEHICLE_IDS.
    mock_abrp_client.return_value = [
        _make_vehicle(MOCK_VEHICLE_ID, "MG4", _VEHICLE_MODEL_V1),
        _make_vehicle(_NEW_VEHICLE_ID, "Brand New Vehicle", _VEHICLE_MODEL_V1),
    ]
    await _poll(hass, entry)

    assert entry.state is ConfigEntryState.LOADED

    # No device created for the new vehicle: it's known-but-not-selected.
    new_scope = _device_scope(entry, _NEW_VEHICLE_ID)
    assert device_registry.async_get_device(identifiers={(DOMAIN, new_scope)}) is None


# ---------------------------------------------------------------------------
# Vehicle disappears mid-life robustness
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_vehicle_disappears_mid_life_does_not_crash(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A vehicle falling out of a poll must not crash the rename listener.

    The listener iterates only the vehicles present in the *current*
    ``coordinator.data``.  A vehicle that was registered in the initial poll
    but absent from a later poll is simply not iterated — its device survives
    unchanged.

    Asserts:
    - Entry remains LOADED.
    - Orphaned device's ``name`` is unchanged (listener never touched it).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: [str(MOCK_VEHICLE_ID), str(MOCK_VEHICLE_ID_2)],
        },
    )

    vehicle_a = _make_vehicle(MOCK_VEHICLE_ID, "Vehicle A", _VEHICLE_MODEL_V1)
    vehicle_b = _make_vehicle(MOCK_VEHICLE_ID_2, "Vehicle B", _VEHICLE_MODEL_V1)
    mock_abrp_client.return_value = [vehicle_a, vehicle_b]
    await _setup_integration(hass, entry)

    scope_b = _device_scope(entry, MOCK_VEHICLE_ID_2)
    device_b = device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
    assert device_b is not None
    assert device_b.name == "Vehicle B"

    # Poll 2: vehicle B disappears from ABRP.
    mock_abrp_client.return_value = [vehicle_a]
    await _poll(hass, entry)

    assert entry.state is ConfigEntryState.LOADED

    # Orphaned device B must be untouched — name unchanged, device still present
    device_b = device_registry.async_get_device(identifiers={(DOMAIN, scope_b)})
    assert device_b is not None
    assert device_b.name == "Vehicle B"


# ---------------------------------------------------------------------------
# device model / manufacturer propagation (late catalog recovery)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("fake_stream")
async def test_display_recovery_updates_device_model_without_reload(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Late display recovery updates device model + manufacturer in place.

    No config-entry reload is required. Mirrors the real ABRP
    feature-plan-entitlement-lag case: the display endpoint 404s during
    setup so the device card falls back to the raw typecode (and an unset
    manufacturer), then the endpoint recovers on the next poll.
    ``_propagate_device_metadata`` pushes the composed model/manufacturer into
    the registry on that same poll. The user-facing name is unaffected.
    """
    mock_abrp_client.return_value = [
        _make_vehicle(MOCK_VEHICLE_ID, "My R2", MOCK_VEHICLE_MODEL)
    ]
    # First setup poll: display_responses is empty → 404 for every typecode.
    await _setup_integration(hass, config_entry_with_vehicles)

    scope = _device_scope(config_entry_with_vehicles, MOCK_VEHICLE_ID)
    device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
    assert device is not None
    # Setup hit the 404 → raw-typecode + unset manufacturer.
    assert device.model == MOCK_VEHICLE_MODEL
    assert device.manufacturer is None

    # Next poll: display recovers → model/manufacturer propagate in place.
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = (
        build_vehicle_model_display()
    )
    await _poll(hass, config_entry_with_vehicles)

    device = device_registry.async_get_device(identifiers={(DOMAIN, scope)})
    assert device is not None
    assert device.manufacturer == "Rivian"
    assert device.model == "Rivian R2 2026 Standard Long Range RWD"
    # The user-facing name is unaffected by the model recovery.
    assert device.name == "My R2"
