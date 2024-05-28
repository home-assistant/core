"""Fixtures for the Whirlpool Sixth Sense integration tests."""

from unittest import mock
from unittest.mock import AsyncMock, MagicMock

import pytest
import whirlpool
import whirlpool.aircon
from whirlpool.backendselector import Brand, Region

MOCK_SAID1 = "said1"
MOCK_SAID2 = "said2"
MOCK_SAID3 = "said3"
MOCK_SAID4 = "said4"


@pytest.fixture(
    name="region",
    params=[("EU", Region.EU), ("US", Region.US)],
)
def fixture_region(request):
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
def fixture_brand(request):
    """Return a brand for input."""
    return request.param


@pytest.fixture(name="mock_auth_api")
def fixture_mock_auth_api():
    """Set up Auth fixture."""
    with mock.patch("homeassistant.components.whirlpool.Auth") as mock_auth:
        mock_auth.return_value.do_auth = AsyncMock()
        mock_auth.return_value.is_access_token_valid.return_value = True
        yield mock_auth


@pytest.fixture(name="mock_appliances_manager_api")
def fixture_mock_appliances_manager_api():
    """Set up AppliancesManager fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.AppliancesManager"
    ) as mock_appliances_manager:
        mock_appliances_manager.return_value.fetch_appliances = AsyncMock()
        mock_appliances_manager.return_value.aircons = [
            {"SAID": MOCK_SAID1, "NAME": "TestZone"},
            {"SAID": MOCK_SAID2, "NAME": "TestZone"},
        ]
        mock_appliances_manager.return_value.washer_dryers = [
            {"SAID": MOCK_SAID3, "NAME": "washer"},
            {"SAID": MOCK_SAID4, "NAME": "dryer"},
        ]
        yield mock_appliances_manager


@pytest.fixture(name="mock_appliances_manager_laundry_api")
def fixture_mock_appliances_manager_laundry_api():
    """Set up AppliancesManager fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.AppliancesManager"
    ) as mock_appliances_manager:
        mock_appliances_manager.return_value.fetch_appliances = AsyncMock()
        mock_appliances_manager.return_value.aircons = None
        mock_appliances_manager.return_value.washer_dryers = [
            {"SAID": MOCK_SAID3, "NAME": "washer"},
            {"SAID": MOCK_SAID4, "NAME": "dryer"},
        ]
        yield mock_appliances_manager


@pytest.fixture(name="mock_backend_selector_api")
def fixture_mock_backend_selector_api():
    """Set up BackendSelector fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.BackendSelector"
    ) as mock_backend_selector:
        yield mock_backend_selector


def get_aircon_mock(said):
    """Get a mock of an air conditioner."""
    mock_aircon = mock.Mock(said=said)
    mock_aircon.connect = AsyncMock()
    mock_aircon.disconnect = AsyncMock()
    mock_aircon.register_attr_callback = MagicMock()
    mock_aircon.get_online.return_value = True
    mock_aircon.get_power_on.return_value = True
    mock_aircon.get_mode.return_value = whirlpool.aircon.Mode.Cool
    mock_aircon.get_fanspeed.return_value = whirlpool.aircon.FanSpeed.Auto
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
def fixture_mock_aircon1_api(mock_auth_api, mock_appliances_manager_api):
    """Set up air conditioner API fixture."""
    return get_aircon_mock(MOCK_SAID1)


@pytest.fixture(name="mock_aircon2_api", autouse=False)
def fixture_mock_aircon2_api(mock_auth_api, mock_appliances_manager_api):
    """Set up air conditioner API fixture."""
    return get_aircon_mock(MOCK_SAID2)


@pytest.fixture(name="mock_aircon_api_instances", autouse=False)
def fixture_mock_aircon_api_instances(mock_aircon1_api, mock_aircon2_api):
    """Set up air conditioner API fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.climate.Aircon"
    ) as mock_aircon_api:
        mock_aircon_api.side_effect = [mock_aircon1_api, mock_aircon2_api]
        yield mock_aircon_api


def side_effect_function(*args, **kwargs):
    """Return correct value for attribute."""
    if args[0] == "Cavity_TimeStatusEstTimeRemaining":
        return 3540
    if args[0] == "Cavity_OpStatusDoorOpen":
        return "0"
    if args[0] == "WashCavity_OpStatusBulkDispense1Level":
        return "3"


def get_sensor_mock(said):
    """Get a mock of a sensor."""
    mock_sensor = mock.Mock(said=said)
    mock_sensor.connect = AsyncMock()
    mock_sensor.disconnect = AsyncMock()
    mock_sensor.register_attr_callback = MagicMock()
    mock_sensor.get_online.return_value = True
    mock_sensor.get_machine_state.return_value = (
        whirlpool.washerdryer.MachineState.Standby
    )
    mock_sensor.get_attribute.side_effect = side_effect_function
    mock_sensor.get_cycle_status_filling.return_value = False
    mock_sensor.get_cycle_status_rinsing.return_value = False
    mock_sensor.get_cycle_status_sensing.return_value = False
    mock_sensor.get_cycle_status_soaking.return_value = False
    mock_sensor.get_cycle_status_spinning.return_value = False
    mock_sensor.get_cycle_status_washing.return_value = False

    return mock_sensor


@pytest.fixture(name="mock_sensor1_api", autouse=False)
def fixture_mock_sensor1_api(mock_auth_api, mock_appliances_manager_laundry_api):
    """Set up sensor API fixture."""
    return get_sensor_mock(MOCK_SAID3)


@pytest.fixture(name="mock_sensor2_api", autouse=False)
def fixture_mock_sensor2_api(mock_auth_api, mock_appliances_manager_laundry_api):
    """Set up sensor API fixture."""
    return get_sensor_mock(MOCK_SAID4)


@pytest.fixture(name="mock_sensor_api_instances", autouse=False)
def fixture_mock_sensor_api_instances(mock_sensor1_api, mock_sensor2_api):
    """Set up sensor API fixture."""
    with mock.patch(
        "homeassistant.components.whirlpool.sensor.WasherDryer"
    ) as mock_sensor_api:
        mock_sensor_api.side_effect = [
            mock_sensor1_api,
            mock_sensor2_api,
            mock_sensor1_api,
            mock_sensor2_api,
        ]
        yield mock_sensor_api
