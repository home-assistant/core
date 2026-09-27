"""Test the Bluetti BT config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetti_bt.const import (
    CONF_ENCRYPTION,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_API_VERSION, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device

DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
DEVICE_NAME = "Bluetti AC200M"
SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"

CONFIG_FLOW_PATH = "homeassistant.components.bluetti_bt.config_flow"

MOCK_DEVICE_DATA = {
    CONF_ADDRESS: DEVICE_ADDRESS,
    CONF_MODEL: "AC200M",
    CONF_SERIAL: "12345",
    CONF_API_VERSION: 1,
    CONF_ENCRYPTION: False,
}


def _service_info(address: str = DEVICE_ADDRESS, name: str = DEVICE_NAME) -> MagicMock:
    """Build a mock BluetoothServiceInfoBleak for discovery."""
    info = MagicMock()
    info.address = address
    info.name = name
    info.service_uuids = [SERVICE_UUID]
    info.device = generate_ble_device(address, name)
    return info


def _mock_recognized_device(
    name: str = "AC200M",
    sn: int = 12345,
    iot_version: int = 1,
    encrypted: bool = False,
) -> MagicMock:
    """Build a mock result as returned by recognize_device()."""
    result = MagicMock()
    result.name = name
    result.sn = sn
    result.iot_version = iot_version
    result.encrypted = encrypted
    return result


async def test_bluetooth_discovery_success(hass: HomeAssistant) -> None:
    """Discovery followed by successful detection creates an entry."""
    with (
        patch(
            f"{CONFIG_FLOW_PATH}.bluetooth.async_ble_device_from_address",
            return_value=generate_ble_device(DEVICE_ADDRESS, DEVICE_NAME),
        ),
        patch(
            f"{CONFIG_FLOW_PATH}.recognize_device",
            AsyncMock(return_value=_mock_recognized_device()),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=_service_info(),
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "AC200M"
    assert result2["data"] == MOCK_DEVICE_DATA


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """A device that is already configured is aborted during discovery."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ADDRESS, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_service_info(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_without_discovery(hass: HomeAssistant) -> None:
    """The user step aborts if it wasn't reached through discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_unconfigured_devices"


async def test_bluetooth_discovery_unreachable(hass: HomeAssistant) -> None:
    """Detection aborts if the BLE device can no longer be reached."""
    with patch(
        f"{CONFIG_FLOW_PATH}.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=_service_info(),
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unreachable"


async def test_bluetooth_discovery_unsupported_device(hass: HomeAssistant) -> None:
    """Detection aborts if the device could not be recognized."""
    with (
        patch(
            f"{CONFIG_FLOW_PATH}.bluetooth.async_ble_device_from_address",
            return_value=generate_ble_device(DEVICE_ADDRESS, DEVICE_NAME),
        ),
        patch(
            f"{CONFIG_FLOW_PATH}.recognize_device",
            AsyncMock(return_value=None),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=_service_info(),
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unsupported_device"


async def test_reconfigure_flow_success(hass: HomeAssistant) -> None:
    """A reconfigure flow updates the entry with freshly detected data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ADDRESS,
        data=MOCK_DEVICE_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            f"{CONFIG_FLOW_PATH}.bluetooth.async_ble_device_from_address",
            return_value=generate_ble_device(DEVICE_ADDRESS, DEVICE_NAME),
        ),
        patch(
            f"{CONFIG_FLOW_PATH}.recognize_device",
            AsyncMock(return_value=_mock_recognized_device(sn=99999)),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SERIAL] == "99999"


async def test_reconfigure_flow_unreachable(hass: HomeAssistant) -> None:
    """A reconfigure flow aborts if the device is unreachable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ADDRESS,
        data=MOCK_DEVICE_DATA,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with patch(
        f"{CONFIG_FLOW_PATH}.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unreachable"
    # Original data must remain untouched.
    assert entry.data == MOCK_DEVICE_DATA
