"""Tests for the Motionblinds Bluetooth integration."""

from motionblindsble.const import MotionBlindType

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.motionblinds_ble import async_setup_entry
from homeassistant.components.motionblinds_ble.const import CONF_LOCAL_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

FIXTURE_MAC = "CCCC"
FIXTURE_NAME = f"MOTION_{FIXTURE_MAC.upper()}"
FIXTURE_ADDRESS = "cc:cc:cc:cc:cc:cc"
FIXTURE_BLIND_TYPE = MotionBlindType.ROLLER.name.lower()

FIXTURE_SERVICE_INFO = BluetoothServiceInfoBleak(
    name=FIXTURE_NAME,
    address=FIXTURE_ADDRESS,
    device=generate_ble_device(
        address=FIXTURE_ADDRESS,
        name=FIXTURE_NAME,
    ),
    rssi=-61,
    manufacturer_data={000: b"test"},
    service_data={
        "test": bytearray(b"0000"),
    },
    service_uuids=[
        "test",
    ],
    source="local",
    advertisement=generate_advertisement_data(
        manufacturer_data={000: b"test"},
        service_uuids=["test"],
    ),
    connectable=True,
    time=0,
    tx_power=-127,
)


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> str:
    """Mock a fully setup config entry."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await async_setup_entry(hass, mock_config_entry)
    await hass.async_block_till_done()

    return str(mock_config_entry.data[CONF_LOCAL_NAME]).lower().replace(" ", "_")
