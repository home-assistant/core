"""Mock inputs for tests."""
from lmcloud.const import LaMarzoccoModel

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

LOGIN_INFO = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

WRONG_LOGIN_INFO = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "wrong_password",
}

HOST_SELECTION = {
    CONF_HOST: "192.168.1.1",
}


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
