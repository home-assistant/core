"""Mock inputs for tests."""

from unittest.mock import AsyncMock, MagicMock

from pylamarzocco.const import ModelName
from pylamarzocco.models import (
    ThingDashboardConfig,
    ThingSchedulingSettings,
    ThingSettings,
    ThingStatistics,
)
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

HOST_SELECTION = {
    CONF_HOST: "192.168.1.1",
}

PASSWORD_SELECTION = {
    CONF_PASSWORD: "password",
}

USER_INPUT = PASSWORD_SELECTION | {CONF_USERNAME: "username"}

SERIAL_DICT = {
    ModelName.GS3_AV: "GS012345",
    ModelName.GS3_MP: "GS012345",
    ModelName.LINEA_MICRA: "MR012345",
    ModelName.LINEA_MINI: "LM012345",
}

WAKE_UP_SLEEP_ENTRY_IDS = ["Os2OswX", "aXFz5bJ"]


async def async_init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the La Marzocco integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def configure_machine_mock(
    machine_mock: MagicMock, model: ModelName, serial_number: str
) -> None:
    """Configure a mocked LaMarzoccoMachine for the given model and serial."""
    if model == ModelName.LINEA_MINI:
        config = load_json_object_fixture("config_mini.json", DOMAIN)
    elif model == ModelName.LINEA_MICRA:
        config = load_json_object_fixture("config_micra.json", DOMAIN)
    else:
        config = load_json_object_fixture("config_gs3.json", DOMAIN)
    schedule = load_json_object_fixture("schedule.json", DOMAIN)
    settings = load_json_object_fixture("settings.json", DOMAIN)
    statistics = load_json_object_fixture("statistics.json", DOMAIN)

    machine_mock.serial_number = serial_number
    machine_mock.dashboard = ThingDashboardConfig.from_dict(config)
    machine_mock.schedule = ThingSchedulingSettings.from_dict(schedule)
    machine_mock.settings = ThingSettings.from_dict(settings)
    machine_mock.statistics = ThingStatistics.from_dict(statistics)
    machine_mock.dashboard.model_name = model
    machine_mock.to_dict.return_value = {
        "serial_number": machine_mock.serial_number,
        "dashboard": machine_mock.dashboard.to_dict(),
        "schedule": machine_mock.schedule.to_dict(),
        "settings": machine_mock.settings.to_dict(),
    }
    machine_mock.connect_dashboard_websocket = AsyncMock()
    machine_mock.websocket = MagicMock()
    machine_mock.websocket.connected = True
    machine_mock.websocket.disconnect = AsyncMock()
    machine_mock.bluetooth_shot_counter_active = False
    machine_mock.bluetooth_connected = True
    machine_mock.register_bluetooth_connection_callback.return_value = MagicMock(
        return_value=None
    )
    machine_mock.connect_bluetooth_shot_counter.return_value = True


def get_bluetooth_service_info(model: ModelName, serial: str) -> BluetoothServiceInfo:
    """Return a mocked BluetoothServiceInfo."""
    if model in (ModelName.GS3_AV, ModelName.GS3_MP):
        name = f"GS3_{serial}"
    elif model == ModelName.LINEA_MINI:
        name = f"MINI_{serial}"
    elif model == ModelName.LINEA_MICRA:
        name = f"MICRA_{serial}"
    return BluetoothServiceInfo(
        name=name,
        address="aa:bb:cc:dd:ee:ff",
        rssi=-63,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
    )


MOCK_INSTALLATION_KEY = (
    '{"secret": "K9ZW2vlMSb3QXmhySx4pxAbTHujWj3VZ01Jn3D/sO98=",'
    ' "private_key":'
    ' "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg8iotE8El786F'
    "6kHuEL8GyYhjDB7oo06vNhQwtewF37yhRANCAAQCLb9lHskiavvfkI4H2B"
    "+WsdkusfgBBFuFNRrGV8bqPMra1TK5myb/ecdZfHJBBJrcbdt90QMDmXQm5L3"
    'muXXe",'
    ' "installation_id": "4e966f3f-2abc-49c4-a362-3cd3346f1a87"}'
)
