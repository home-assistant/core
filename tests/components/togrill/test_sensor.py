"""Test sensors for ToGrill integration."""

from unittest.mock import Mock, patch

from habluetooth import BluetoothServiceInfoBleak
import pytest
from syrupy.assertion import SnapshotAssertion
from togrill_bluetooth.packets import PacketA0Notify, PacketA1Notify

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TOGRILL_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


def patch_async_ble_device_from_address(
    return_value: BluetoothServiceInfoBleak | None = None,
):
    """Patch async_ble_device_from_address to return a mocked BluetoothServiceInfoBleak."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=return_value,
    )


@pytest.mark.parametrize(
    "packets",
    [
        pytest.param([], id="no_data"),
        pytest.param(
            [
                PacketA0Notify(
                    battery=45,
                    version_major=1,
                    version_minor=5,
                    function_type=1,
                    probe_count=2,
                    ambient=False,
                    alarm_interval=5,
                    alarm_sound=True,
                )
            ],
            id="battery",
        ),
        pytest.param([PacketA1Notify([10, None])], id="temp_data"),
        pytest.param([PacketA1Notify([10])], id="temp_data_missing_probe"),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    packets,
) -> None:
    """Test the sensors."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SENSOR])

    for packet in packets:
        mock_client.mocked_notify(packet)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


async def test_device_disconnected(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switch set."""
    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SENSOR])

    entity_id = "sensor.pro_05_battery"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0"

    with patch_async_ble_device_from_address():
        mock_client.mocked_disconnected_callback()
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"


async def test_device_discovered(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the switch set."""

    await setup_entry(hass, mock_entry, [Platform.SENSOR])

    entity_id = "sensor.pro_05_battery"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0"
