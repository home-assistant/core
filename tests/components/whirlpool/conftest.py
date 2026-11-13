"""Fixtures for the Whirlpool Sixth Sense integration tests."""

from unittest import mock
from unittest.mock import Mock

import pytest
from whirlpool import (
    aircon,
    appliance,
    appliancesmanager,
    auth,
    dryer,
    microwave,
    oven,
    refrigerator,
    washer,
)
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
    mock_aircon1_api,
    mock_aircon2_api,
    mock_washer_api,
    mock_dryer_api,
    mock_oven_single_cavity_api,
    mock_oven_dual_cavity_api,
    mock_microwave_api,
    mock_refrigerator_api,
    mock_unsupported_appliance_api,
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
        mock_appliances_manager.return_value.washers = [mock_washer_api]
        mock_appliances_manager.return_value.dryers = [mock_dryer_api]
        mock_appliances_manager.return_value.ovens = [
            mock_oven_single_cavity_api,
            mock_oven_dual_cavity_api,
        ]
        mock_appliances_manager.return_value.refrigerators = [mock_refrigerator_api]
        mock_appliances_manager.return_value.microwaves = [mock_microwave_api]
        mock_appliances_manager.return_value.unsupported_appliances = [
            mock_unsupported_appliance_api
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
        category="aircon", model_number="12345", raw_info={}
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
    mock_aircon.get_raw_data.return_value = {
        "_id": said,
        "attributes": {
            "Cavity_OpSetHorzLouverSwing": {"value": "1", "updateTime": 1626517992782},
        },
    }

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
    mock_washer = Mock(spec=washer.Washer, said="said_washer")
    mock_washer.name = "Washer"
    mock_washer.appliance_info = Mock(
        category="washer_dryer",
        model_number="12345",
        raw_info={
            "APPLIANCE_ID": 1033050,
            "APPLIANCE_NAME": "Washer",
            "CATEGORY_NAME": "FabricCare",
            "DATA_MODEL_KEY": "DDM_LAUNDRY_VMAX20_WHIRLPOOL_WASHER8_V2",
            "DEVICE_ID": "550e8400-e29b-41d4-a716-446655441234",
            "LOCATION_ID": 15862310,
            "MACHINE_ID": None,
            "MODEL_NO": "12345",
            "NEST_THERMOSTAT_ID": 0,
            "SAID": "said_washer",
            "SERIAL": "CC26012420",
            "STATUS": "CLAIMED",
        },
    )
    mock_washer.get_online.return_value = True
    mock_washer.get_machine_state.return_value = washer.MachineState.RunningMainCycle
    mock_washer.get_door_open.return_value = False
    mock_washer.get_dispense_1_level.return_value = 3
    mock_washer.get_time_remaining.return_value = 3540
    mock_washer.get_cycle_status_filling.return_value = False
    mock_washer.get_cycle_status_rinsing.return_value = False
    mock_washer.get_cycle_status_sensing.return_value = False
    mock_washer.get_cycle_status_soaking.return_value = False
    mock_washer.get_cycle_status_spinning.return_value = False
    mock_washer.get_cycle_status_washing.return_value = False
    mock_washer.get_raw_data.return_value = {
        "_id": "WBR123456789",
        "attributes": {
            "Cavity_OpSetHorzLouverSwing": {"value": "1", "updateTime": 1626517992782},
        },
    }

    return mock_washer


@pytest.fixture
def mock_dryer_api():
    """Get a mock of a dryer."""
    mock_dryer = mock.Mock(spec=dryer.Dryer, said="said_dryer")
    mock_dryer.name = "Dryer"
    mock_dryer.appliance_info = Mock(
        category="washer_dryer", model_number="12345", raw_info={}
    )
    mock_dryer.get_online.return_value = True
    mock_dryer.get_machine_state.return_value = dryer.MachineState.RunningMainCycle
    mock_dryer.get_door_open.return_value = False
    mock_dryer.get_time_remaining.return_value = 3540
    mock_dryer.get_cycle_status_sensing.return_value = False
    mock_dryer.get_raw_data.return_value = {
        "_id": "WBR123456789",
        "attributes": {
            "Cavity_OpSetHorzLouverSwing": {"value": "1", "updateTime": 1626517992782},
        },
    }
    return mock_dryer


@pytest.fixture
def mock_oven_single_cavity_api():
    """Get a mock of a single cavity oven."""
    mock_oven = Mock(spec=oven.Oven, said="said_oven_single")
    mock_oven.name = "Single Cavity Oven"
    mock_oven.appliance_info = Mock(category="oven", model_number="12345", raw_info={})
    mock_oven.get_cavity_state.return_value = oven.CavityState.Standby
    mock_oven.get_cook_mode.return_value = oven.CookMode.Bake
    mock_oven.get_online.return_value = True
    mock_oven.get_oven_cavity_exists.side_effect = lambda cavity: (
        cavity == oven.Cavity.Upper
    )
    mock_oven.get_light.return_value = True
    mock_oven.get_temp.return_value = 180
    mock_oven.get_target_temp.return_value = 200
    mock_oven.get_raw_data.return_value = {
        "_id": "WBR123456789",
        "attributes": {
            "Cavity_OpSetHorzLouverSwing": {"value": "1", "updateTime": 1626517992782},
        },
    }
    return mock_oven


@pytest.fixture
def mock_oven_dual_cavity_api():
    """Get a mock of a dual cavity oven."""
    mock_oven = Mock(spec=oven.Oven, said="said_oven_dual")
    mock_oven.name = "Dual Cavity Oven"
    mock_oven.appliance_info = Mock(category="oven", model_number="12345", raw_info={})
    mock_oven.get_cavity_state.return_value = oven.CavityState.Standby
    mock_oven.get_cook_mode.return_value = oven.CookMode.Bake
    mock_oven.get_online.return_value = True
    mock_oven.get_oven_cavity_exists.side_effect = lambda cavity: (
        cavity
        in (
            oven.Cavity.Upper,
            oven.Cavity.Lower,
        )
    )
    mock_oven.get_light.side_effect = lambda cavity: cavity == oven.Cavity.Upper
    mock_oven.get_temp.return_value = 180
    mock_oven.get_target_temp.return_value = 200
    mock_oven.get_raw_data.return_value = {
        "_id": "WBR123456789",
        "attributes": {
            "Cavity_OpSetHorzLouverSwing": {"value": "1", "updateTime": 1626517992782},
        },
    }
    return mock_oven


@pytest.fixture
def mock_microwave_api():
    """Get a mock of a microwave."""
    mock_microwave = Mock(spec=microwave.Microwave, said="said_microwave")
    mock_microwave.name = "Microwave"
    mock_microwave.appliance_info = Mock(
        category="microwave",
        model_number="12345",
        raw_info={
            "attributes": {
                "Category": "Cooking",
                "Name": "4d6963726f77617665",
                "Serial": "M1",
            },
            "defaultClientId": "said_microwave",
            "thingArn": "arn:aws:iot:eu-central-1:123456789012:thing/said_microwave",
            "thingId": "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
            "thingName": "said_microwave",
            "thingTypeName": "12345",
            "version": 1,
        },
    )
    mock_microwave.get_raw_data.return_value = {
        "microwaveCavity": {"cavityState": "idle", "doorStatus": "closed"},
        "temperatureUnit": "C",
    }
    return mock_microwave


@pytest.fixture
def mock_refrigerator_api():
    """Get a mock of a refrigerator."""
    mock_refrigerator = Mock(spec=refrigerator.Refrigerator, said="said_refrigerator")
    mock_refrigerator.name = "Beer fridge"
    mock_refrigerator.appliance_info = Mock(
        category="refrigerator", model_number="12345", raw_info={}
    )
    mock_refrigerator.get_offset_temp.return_value = 0
    mock_refrigerator.get_raw_data.return_value = {
        "_id": "WBR123456789",
        "attributes": {
            "Cavity_OpSetHorzLouverSwing": {"value": "1", "updateTime": 1626517992782},
        },
    }
    return mock_refrigerator


@pytest.fixture
def mock_unsupported_appliance_api():
    """Get a mock of an appliance not supported by the library."""
    mock_appliance = Mock(spec=appliance.Appliance, said="said_unsupported")
    mock_appliance.name = "Unsupported appliance"
    mock_appliance.appliance_info = Mock(
        category="cooking",
        model_number="12345",
        raw_info={
            "attributes": {
                "CapabilityPartNumber": "W11788386",
                "Category": "Cooking",
                "Name": "556e737570706f72746564206170706c69616e6365",
                "Serial": "D1",
            },
            "defaultClientId": "said_unsupported",
            "thingArn": "arn:aws:iot:eu-central-1:123456789012:thing/said_unsupported",
            "thingId": "6d3b1a2c-4f5e-4d7a-9b8c-0e1f2a3b4c5d",
            "thingName": "said_unsupported",
            "thingTypeName": "12345",
            "version": 1,
        },
    )
    mock_appliance.get_raw_data.return_value = {
        "primaryCavity": {"cavityState": "idle", "doorStatus": "closed"},
        "temperatureUnit": "C",
    }
    return mock_appliance
