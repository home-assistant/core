"""Test the ENGIE Belgium datetime platform."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from aioengiebelgium import (
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    EngieBeError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.datetime import ATTR_DATETIME, DOMAIN as DATETIME_DOMAIN
from homeassistant.components.engie_be.const import VEHICLES_SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    VEHICLE_ID,
    VEHICLE_WITHOUT_SESSION_ID,
    build_charge_settings,
    build_charge_settings_for_vehicle,
    build_vehicles,
    setup_entry,
)

ENTITY_ID = "datetime.my_car_departure_time"
NOW = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def frozen_now(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time so the 7-day limit is deterministic."""
    freezer.move_to(NOW)


@pytest.fixture(autouse=True)
def vehicles(mock_engie_client: MagicMock) -> None:
    """Return the test vehicles from the mocked ENGIE client."""
    mock_engie_client.return_value.async_get_electric_vehicles.return_value = (
        build_vehicles()
    )


@pytest.mark.usefixtures("mock_engie_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test only the active Smart Charge vehicle with a session gets an entity."""
    with patch("homeassistant.components.engie_be._PLATFORMS", [Platform.DATETIME]):
        await setup_entry(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test setting the departure sends it to ENGIE and updates the state."""
    client = mock_engie_client.return_value
    new_departure = NOW + timedelta(days=3)
    client.async_update_latest_charging_session_charge_settings.return_value = (
        build_charge_settings(new_departure)
    )
    await setup_entry(hass, mock_config_entry)

    await hass.services.async_call(
        DATETIME_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_DATETIME: new_departure.isoformat()},
        blocking=True,
    )

    client.async_update_latest_charging_session_charge_settings.assert_awaited_once_with(
        VEHICLE_ID,
        departure_time_override=new_departure,
        target_battery_level=80,
        direct=False,
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == new_departure.isoformat()


async def test_set_value_too_far(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test a departure more than 7 days ahead is rejected without calling ENGIE."""
    client = mock_engie_client.return_value
    await setup_entry(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="at most 7 days"):
        await hass.services.async_call(
            DATETIME_DOMAIN,
            "set_value",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_DATETIME: (NOW + timedelta(days=7, hours=1)).isoformat(),
            },
            blocking=True,
        )

    client.async_update_latest_charging_session_charge_settings.assert_not_awaited()


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        pytest.param(
            EngieBeAuthenticationError("denied"),
            "Authentication with ENGIE Belgium failed",
            id="auth",
        ),
        pytest.param(
            EngieBeCommunicationError("boom"),
            "connection error",
            id="communication",
        ),
    ],
)
async def test_set_value_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    exception: EngieBeError,
    message: str,
) -> None:
    """Test an API failure surfaces as a translated error and keeps the state."""
    client = mock_engie_client.return_value
    client.async_update_latest_charging_session_charge_settings.side_effect = exception
    await setup_entry(hass, mock_config_entry)
    before = hass.states.get(ENTITY_ID)

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DATETIME_DOMAIN,
            "set_value",
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_DATETIME: (NOW + timedelta(days=1)).isoformat(),
            },
            blocking=True,
        )

    assert hass.states.get(ENTITY_ID) == before


async def test_unavailable_without_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity follows the session: unavailable when it ends, back when it returns."""
    client = mock_engie_client.return_value
    await setup_entry(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    client.async_get_latest_charging_session_charge_settings.side_effect = (
        EngieBeCommunicationError("not found", status=404)
    )
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    client.async_get_latest_charging_session_charge_settings.side_effect = (
        build_charge_settings_for_vehicle
    )
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_entity_added_when_session_starts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a vehicle that gets a Smart Charge session later gets its entity."""
    client = mock_engie_client.return_value
    await setup_entry(hass, mock_config_entry)
    assert (
        entity_registry.async_get_entity_id(
            "datetime", "engie_be", f"{VEHICLE_WITHOUT_SESSION_ID}_departure_time"
        )
        is None
    )

    client.async_get_latest_charging_session_charge_settings.side_effect = (
        lambda _vehicle_id: build_charge_settings()
    )
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            "datetime", "engie_be", f"{VEHICLE_WITHOUT_SESSION_ID}_departure_time"
        )
        is not None
    )


async def test_vehicles_error_makes_entity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing refresh makes the entity unavailable."""
    client = mock_engie_client.return_value
    await setup_entry(hass, mock_config_entry)

    client.async_get_electric_vehicles.side_effect = EngieBeCommunicationError("boom")
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_vehicles_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an auth error during a vehicles refresh starts reauth."""
    client = mock_engie_client.return_value
    await setup_entry(hass, mock_config_entry)

    client.async_get_electric_vehicles.side_effect = EngieBeAuthenticationError(
        "denied"
    )
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("engie_be")
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_settings_error_makes_entity_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a settings error other than a missing session fails the whole refresh."""
    client = mock_engie_client.return_value
    await setup_entry(hass, mock_config_entry)

    client.async_get_latest_charging_session_charge_settings.side_effect = (
        EngieBeCommunicationError("boom", status=500)
    )
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_entity_added_after_failed_setup_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the entity appears once a refresh succeeds after a failed first one."""
    client = mock_engie_client.return_value
    client.async_get_electric_vehicles.side_effect = EngieBeCommunicationError("boom")
    await setup_entry(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID) is None

    client.async_get_electric_vehicles.side_effect = None
    freezer.tick(VEHICLES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is not None
