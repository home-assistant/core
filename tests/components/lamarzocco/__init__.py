"""Mock inputs for tests."""

from lmcloud.const import LaMarzoccoModel

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

HOST_SELECTION = {
    CONF_HOST: "192.168.1.1",
}

PASSWORD_SELECTION = {
    CONF_PASSWORD: "password",
}

USER_INPUT = PASSWORD_SELECTION | {CONF_USERNAME: "username"}

MODEL_DICT = {
    LaMarzoccoModel.GS3_AV: ("GS01234", "GS3 AV"),
    LaMarzoccoModel.GS3_MP: ("GS01234", "GS3 MP"),
    LaMarzoccoModel.LINEA_MICRA: ("MR01234", "Linea Micra"),
    LaMarzoccoModel.LINEA_MINI: ("LM01234", "Linea Mini"),
}


async def async_init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the La Marzocco integration for testing."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def get_bluetooth_service_info(
    model: LaMarzoccoModel, serial: str
) -> BluetoothServiceInfo:
    """Return a mocked BluetoothServiceInfo."""
    if model in (LaMarzoccoModel.GS3_AV, LaMarzoccoModel.GS3_MP):
        name = f"GS3_{serial}"
    elif model == LaMarzoccoModel.LINEA_MINI:
        name = f"MINI_{serial}"
    elif model == LaMarzoccoModel.LINEA_MICRA:
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
