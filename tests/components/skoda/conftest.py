"""Common fixtures for the Škoda tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from skoda_public_api.models.air_conditioning import AirConditioning
from skoda_public_api.models.auxiliary_heating import AuxiliaryHeating
from skoda_public_api.models.charging import (
    BatteryStatus,
    Charging,
    ChargingSettings,
    ChargingStatus,
)
from skoda_public_api.models.common import TargetTemperature
from skoda_public_api.models.driving_range import EngineRange, FuelStatus
from skoda_public_api.models.enums import (
    AirConditioningState,
    AutoUnlockPlugState,
    AuxiliaryHeatingState,
    ChargeType,
    ChargingState,
    DoorsState,
    LockState,
    OnOffState,
    OpenCloseState,
    TemperatureUnit,
    YesNoState,
)
from skoda_public_api.models.vehicle import Odometer, VehicleObject, VehicleResponse
from skoda_public_api.models.vehicle_status import (
    OverallVehicleStatus,
    VehicleStatus,
    VehicleStatusDetail,
)

from homeassistant.components.skoda.const import CONF_VIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

VIN = "TMBJM7NP2M1TMP511"
API_KEY = "test-api-key"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.skoda.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Škoda config entry."""
    return MockConfigEntry(
        domain="skoda",
        title="Škoda Enyaq Coupé",
        unique_id=VIN,
        data={CONF_VIN: VIN, CONF_API_KEY: API_KEY},
    )


@pytest.fixture
def mock_vehicle_response() -> VehicleResponse:
    """Return a fully-populated vehicle response for entity/sensor tests."""
    return VehicleResponse(
        vehicle=VehicleObject(
            name="Enyaq Coupé",
            vin=VIN,
            license_plate="EL107FP",
            odometer=Odometer(mileage_in_km=9618, car_captured_timestamp=None),
            status=VehicleStatus(
                overall=OverallVehicleStatus(
                    doors_locked=DoorsState.NO,
                    locked=YesNoState.YES,
                    doors=OpenCloseState.CLOSED,
                    windows=OpenCloseState.CLOSED,
                    lights=OnOffState.OFF,
                    reliable_lock_status=LockState.LOCKED,
                ),
                detail=VehicleStatusDetail(
                    sunroof=OpenCloseState.CLOSED,
                    trunk=OpenCloseState.CLOSED,
                    bonnet=OpenCloseState.CLOSED,
                ),
            ),
            charging=Charging(
                is_vehicle_in_saved_location=False,
                status=ChargingStatus(
                    charging_rate_in_kilometers_per_hour=20.0,
                    charge_power_in_kw=11.0,
                    remaining_time_to_fully_charged_in_minutes=45,
                    state=ChargingState.CHARGING,
                    charge_type=ChargeType.AC,
                    battery=BatteryStatus(
                        remaining_cruising_range_in_meters=513000,
                        state_of_charge_in_percent=99,
                    ),
                ),
                settings=ChargingSettings(
                    target_state_of_charge_in_percent=80,
                    auto_unlock_plug_when_charged=AutoUnlockPlugState.OFF,
                ),
            ),
            fuel_status=FuelStatus(
                car_type="ELECTRIC",
                total_range_in_km=513,
                primary_engine_range=EngineRange(
                    engine_type="ELECTRIC",
                    current_soc_in_percent=99,
                    remaining_range_in_km=513,
                ),
            ),
            air_conditioning=AirConditioning(
                state=AirConditioningState.OFF,
                target_temperature=TargetTemperature(
                    value=21.5, unit=TemperatureUnit.CELSIUS
                ),
            ),
            auxiliary_heating=AuxiliaryHeating(
                state=AuxiliaryHeatingState.OFF,
                duration_in_seconds=1200,
            ),
        )
    )


@pytest.fixture
def mock_get_vehicle(mock_vehicle_response: VehicleResponse) -> Generator[AsyncMock]:
    """Mock OpenAPIClient.get_vehicle used during integration setup."""
    with patch(
        "homeassistant.components.skoda.OpenAPIClient.get_vehicle",
        AsyncMock(return_value=mock_vehicle_response),
    ) as mock:
        yield mock
