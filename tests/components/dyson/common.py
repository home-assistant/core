"""Common utils for Dyson tests."""

from unittest import mock

from libpurecool.dyson_pure_cool import FanSpeed


def load_mock_device(device):
    """Load the mock with default values so it doesn't throw errors."""
    device.serial = "XX-XXXXX-XX"
    device.name = "Temp Name"
    device.connect = mock.Mock(return_value=True)
    device.auto_connect = mock.Mock(return_value=True)
    device.environmental_state.particulate_matter_25 = "0000"
    device.environmental_state.particulate_matter_10 = "0000"
    device.environmental_state.nitrogen_dioxide = "0000"
    device.environmental_state.volatil_organic_compounds = "0000"
    device.environmental_state.volatile_organic_compounds = "0000"
    device.environmental_state.temperature = 250
    device.state.hepa_filter_state = 0
    device.state.carbon_filter_state = 0
    device.state.speed = FanSpeed.FAN_SPEED_1.value
    device.state.oscillation_angle_low = "000"
    device.state.oscillation_angle_high = "000"
    device.state.filter_life = "000"
    device.state.heat_target = 200
