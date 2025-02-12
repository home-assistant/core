"""Test configuration and mocks for the SmartThings component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pysmartthings.models import DeviceResponse, DeviceStatus, SceneResponse
import pytest

from homeassistant.components.smartthings.const import CONF_LOCATION_ID, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smartthings.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_smartthings() -> Generator[AsyncMock]:
    """Mock a SmartThings client."""
    with (
        patch(
            "homeassistant.components.smartthings.SmartThings",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.get_scenes.return_value = SceneResponse.from_json(
            load_fixture("scenes.json", DOMAIN)
        ).items
        yield client


@pytest.fixture(
    params=[
        "da_ac_rac_000001",
        "da_ac_rac_01001",
        "multipurpose_sensor",
        "contact_sensor",
        "base_electric_meter",
        "smart_plug",
        "vd_stv_2017_k",
        "c2c_arlo_pro_3_switch",
        "yale_push_button_deadbolt_lock",
        "ge_in_wall_smart_dimmer",
        "centralite",
        "da_ref_normal_000001",
        "vd_network_audio_002s",
        "iphone",
        "da_wm_dw_000001",
        "da_wm_wd_000001",
        "da_wm_wm_000001",
        "da_rvc_normal_000001",
        "da_ks_microwave_0101x",
        "hue_color_temperature_bulb",
        "hue_rgbw_color_bulb",
        "c2c_shade",
        "sonos_player",
        "aeotec_home_energy_meter_gen5",
        "virtual_water_sensor",
        "virtual_thermostat",
        "virtual_valve",
        "sensibo_airconditioner_1",
        "ecobee_sensor",
        "ecobee_thermostat",
    ]
)
def fixture(
    mock_smartthings: AsyncMock, request: pytest.FixtureRequest
) -> Generator[str]:
    """Return every device."""
    return request.param


@pytest.fixture
def devices(mock_smartthings: AsyncMock, fixture: str) -> Generator[AsyncMock]:
    """Return a specific device."""
    mock_smartthings.get_devices.return_value = DeviceResponse.from_json(
        load_fixture(f"devices/{fixture}.json", DOMAIN)
    ).items
    mock_smartthings.get_device_status.return_value = DeviceStatus.from_json(
        load_fixture(f"device_status/{fixture}.json", DOMAIN)
    ).components
    return mock_smartthings


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="SmartThings",
        data={CONF_ACCESS_TOKEN: "abc", CONF_LOCATION_ID: "123"},
        version=3,
    )
