"""Fixtures for the Whirlpool Sixth Sense integration tests."""

from unittest import mock
from unittest.mock import Mock

import pytest
from whirlpool import aircon, appliancesmanager, auth, washerdryer
from whirlpool.backendselector import Brand, Region

from .const import MOCK_SAID1, MOCK_SAID2


@pytest.fixture(
    name="region",
    params=[("EU", Region.EU), ("US", Region.US)],
)
def fixture_region(request: pytest.FixtureRequest) -> tuple[str, Region]:
    """Return a region for input."""
    return request.param


@pytest.fixture(
    name="brand",
    params=[
        ("Whirlpool", Brand.Whirlpool),
        ("KitchenAid", Brand.KitchenAid),
        ("Maytag", Brand.Maytag),
    ],
)
def fixture_brand(request: pytest.FixtureRequest) -> tuple[str, Brand]:
    """Return a brand for input."""
    return request.param


@pytest.fixture(name="mock_auth_api", autouse=True)
def fixture_mock_auth_api():
    """Set up Auth fixture."""
    with (
        mock.patch(
            "homeassistant.components.whirlpool.Auth", spec=auth.Auth
        ) as mock_auth,
        mock.patch(
            "homeassistant.components.whirlpool.config_flow.Auth", new=mock_auth
        ),
    ):
        mock_auth.return_value.is_access_token_valid.return_value = True
        yield mock_auth


@pytest.fixture(name="mock_appliances_manager_api", autouse=True)
def fixture_mock_appliances_manager_api(
    mock_aircon1_api, mock_aircon2_api, mock_washer_api, mock_dryer_api
):
    """Set up AppliancesManager fixture."""
    with (
        mock.patch(
            "homeassistant.components.whirlpool.AppliancesManager",
            spec=appliancesmanager.AppliancesManager,
        ) as mock_appliances_manager,
        mock.patch(
            "homeassistant.components.whirlpool.config_flow.AppliancesManager",
            new=mock_appliances_manager,
        ),
    ):
        mock_appliances_manager.return_value.aircons = [
            mock_aircon1_api,
            mock_aircon2_api,
        ]
        mock_appliances_manager.return_value.washer_dryers = [
            mock_washer_api,
            mock_dryer_api,
        ]
        yield mock_appliances_manager


@pytest.fixture(name="mock_backend_selector_api")
def fixture_mock_backend_selector_api():
    """Set up BackendSelector fixture."""
    with (
        mock.patch(
            "homeassistant.components.whirlpool.BackendSelector"
        ) as mock_backend_selector,
        mock.patch(
            "homeassistant.components.whirlpool.config_flow.BackendSelector",
            new=mock_backend_selector,
        ),
    ):
        yield mock_backend_selector


def get_aircon_mock(said):
    """Get a mock of an air conditioner."""
    mock_aircon = Mock(spec=aircon.Aircon, said=said)
    mock_aircon.name = f"Aircon {said}"
    mock_aircon.appliance_info = Mock(
        data_model="aircon_model", category="aircon", model_number="12345"
    )
    mock_aircon.get_online.return_value = True
    mock_aircon.get_power_on.return_value = True
    mock_aircon.get_mode.return_value = aircon.Mode.Cool
    mock_aircon.get_fanspeed.return_value = aircon.FanSpeed.Auto
    mock_aircon.get_current_temp.return_value = 15
    mock_aircon.get_temp.return_value = 20
    mock_aircon.get_current_humidity.return_value = 80
    mock_aircon.get_humidity.return_value = 50
    mock_aircon.get_h_louver_swing.return_value = True

    return mock_aircon


@pytest.fixture(name="mock_aircon1_api", autouse=False)
def fixture_mock_aircon1_api():
    """Set up air conditioner API fixture."""
    return get_aircon_mock(MOCK_SAID1)


@pytest.fixture(name="mock_aircon2_api", autouse=False)
def fixture_mock_aircon2_api():
    """Set up air conditioner API fixture."""
    return get_aircon_mock(MOCK_SAID2)


@pytest.fixture
def mock_washer_api():
    """Get a mock of a washer."""
    mock_washer = Mock(spec=washerdryer.WasherDryer, said="said_washer")
    mock_washer.name = "Washer"
    mock_washer.appliance_info = Mock(
        data_model="washer", category="washer_dryer", model_number="12345"
    )
    mock_washer.get_online.return_value = True
    mock_washer.get_machine_state.return_value = (
        washerdryer.MachineState.RunningMainCycle
    )
    mock_washer.get_door_open.return_value = False
    mock_washer.get_dispense_1_level.return_value = 3
    mock_washer.get_time_remaining.return_value = 3540
    mock_washer.get_cycle_status_filling.return_value = False
    mock_washer.get_cycle_status_rinsing.return_value = False
    mock_washer.get_cycle_status_sensing.return_value = False
    mock_washer.get_cycle_status_soaking.return_value = False
    mock_washer.get_cycle_status_spinning.return_value = False
    mock_washer.get_cycle_status_washing.return_value = False

    return mock_washer


@pytest.fixture
def mock_dryer_api():
    """Get a mock of a dryer."""
    mock_dryer = mock.Mock(spec=washerdryer.WasherDryer, said="said_dryer")
    mock_dryer.name = "Dryer"
    mock_dryer.appliance_info = Mock(
        data_model="dryer", category="washer_dryer", model_number="12345"
    )
    mock_dryer.get_online.return_value = True
    mock_dryer.get_machine_state.return_value = (
        washerdryer.MachineState.RunningMainCycle
    )
    mock_dryer.get_door_open.return_value = False
    mock_dryer.get_time_remaining.return_value = 3540
    mock_dryer.get_cycle_status_filling.return_value = False
    mock_dryer.get_cycle_status_rinsing.return_value = False
    mock_dryer.get_cycle_status_sensing.return_value = False
    mock_dryer.get_cycle_status_soaking.return_value = False
    mock_dryer.get_cycle_status_spinning.return_value = False
    mock_dryer.get_cycle_status_washing.return_value = False
    return mock_dryer
