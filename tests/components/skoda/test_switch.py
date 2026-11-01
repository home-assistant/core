"""Test the Škoda switch platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from skoda_public_api.api_layer.exceptions import (
    OpenApiError,
    OpenApiRateLimitError,
    OpenApiUnsupportedError,
)
from skoda_public_api.models.vehicle import VehicleResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.skoda.const import DOMAIN
from homeassistant.components.skoda.coordinator import UPDATE_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import VIN

CHARGING_SWITCH = "switch.enyaq_coupe_charging"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the switch platform."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    "vehicle_fixture", ["vehicle_electric.json", "vehicle_hybrid.json"]
)
async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda switch entities against a snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_combustion.json"])
async def test_no_switches_without_charging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no switches are created for a vehicle without charging data."""
    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("service", "method", "assumed_state"),
    [
        pytest.param(SERVICE_TURN_OFF, "stop_charging", STATE_OFF, id="turn_off"),
        pytest.param(SERVICE_TURN_ON, "start_charging", STATE_ON, id="turn_on"),
    ],
)
async def test_charging_switch_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    service: str,
    method: str,
    assumed_state: str,
) -> None:
    """Test the charging switch sends the command and assumes the new state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: CHARGING_SWITCH},
        blocking=True,
    )

    getattr(mock_skoda_client, method).assert_awaited_once_with(VIN)
    assert (state := hass.states.get(CHARGING_SWITCH))
    assert state.state == assumed_state

    # The next update replaces the assumed state with the one the vehicle reports.
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CHARGING_SWITCH))
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(
            OpenApiRateLimitError(), "rate_limit_exceeded", id="rate_limit_exceeded"
        ),
        pytest.param(OpenApiUnsupportedError(), "command_failed", id="unsupported"),
        pytest.param(OpenApiError("Boom"), "command_failed", id="api_error"),
    ],
)
async def test_charging_switch_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    error: OpenApiError,
    translation_key: str,
) -> None:
    """Test a failed command raises and keeps the reported state."""
    await setup_integration(hass, mock_config_entry)
    mock_skoda_client.stop_charging.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: CHARGING_SWITCH},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert (state := hass.states.get(CHARGING_SWITCH))
    assert state.state == STATE_ON


async def test_charging_switch_unknown_when_charging_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charging switch reports unknown when a later update lacks charging data."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(CHARGING_SWITCH))
    assert state.state == STATE_ON

    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(
        await async_load_json_object_fixture(hass, "vehicle_unavailable.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CHARGING_SWITCH))
    assert state.state == STATE_UNKNOWN
