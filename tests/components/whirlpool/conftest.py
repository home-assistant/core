"""Fixtures for the Whirlpool Sixth Sense integration tests."""

from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
from whirlpool import aircon, washerdryer
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
        mock.patch("homeassistant.components.whirlpool.Auth") as mock_auth,
        mock.patch(
            "homeassistant.components.whirlpool.config_flow.Auth", new=mock_auth
        ),
    ):
        mock_auth.return_value.do_auth = AsyncMock()
        mock_auth.return_value.is_access_token_valid.return_value = True
        yield mock_auth


@pytest.fixture(name="mock_appliances_manager_api", autouse=True)
def fixture_mock_appliances_manager_api(
    mock_aircon1_api, mock_aircon2_api, mock_washer_api, mock_dryer_api
):
    """Set up AppliancesManager fixture."""
    with (
        mock.patch(
            "homeassistant.components.whirlpool.AppliancesManager"
        ) as mock_appliances_manager,
        mock.patch(
            "homeassistant.components.whirlpool.config_flow.AppliancesManager",
            new=mock_appliances_manager,
        ),
    ):
        mock_appliances_manager.return_value.fetch_appliances = AsyncMock()
        mock_appliances_manager.return_value.connect = AsyncMock()
        mock_appliances_manager.return_value.disconnect = AsyncMock()
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
    mock_aircon = mock.Mock(said=said)
    mock_aircon.name = f"Aircon {said}"
    mock_aircon.register_attr_callback = MagicMock()
    mock_aircon.appliance_info.data_model = "aircon_model"
    mock_aircon.appliance_info.category = "aircon"
    mock_aircon.appliance_info.model_number = "12345"
    mock_aircon.get_online.return_value = True
    mock_aircon.get_power_on.return_value = True
    mock_aircon.get_mode.return_value = aircon.Mode.Cool
    mock_aircon.get_fanspeed.return_value = aircon.FanSpeed.Auto
    mock_aircon.get_current_temp.return_value = 15
    mock_aircon.get_temp.return_value = 20
    mock_aircon.get_current_humidity.return_value = 80
    mock_aircon.get_humidity.return_value = 50
    mock_aircon.get_h_louver_swing.return_value = True

    mock_aircon.set_power_on = AsyncMock()
    mock_aircon.set_mode = AsyncMock()
    mock_aircon.set_temp = AsyncMock()
    mock_aircon.set_humidity = AsyncMock()
    mock_aircon.set_mode = AsyncMock()
    mock_aircon.set_fanspeed = AsyncMock()
    mock_aircon.set_h_louver_swing = AsyncMock()

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
    mock_washer = mock.Mock(said="said_washer")
    mock_washer.name = "Washer"
    mock_washer.fetch_data = AsyncMock()
    mock_washer.register_attr_callback = MagicMock()
    mock_washer.appliance_info.data_model = "washer"
    mock_washer.appliance_info.category = "washer_dryer"
    mock_washer.appliance_info.model_number = "12345"
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
    mock_dryer = mock.Mock(said="said_dryer")
    mock_dryer.name = "Dryer"
    mock_dryer.fetch_data = AsyncMock()
    mock_dryer.register_attr_callback = MagicMock()
    mock_dryer.appliance_info.data_model = "dryer"
    mock_dryer.appliance_info.category = "washer_dryer"
    mock_dryer.appliance_info.model_number = "12345"
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
