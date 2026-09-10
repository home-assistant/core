"""Test Home Assistant Hardware platform for ZHA."""

from unittest.mock import MagicMock, call, patch

import pytest
from zigpy.application import ControllerApplication

from homeassistant.components.homeassistant_hardware import (
    DOMAIN as HOMEASSISTANT_HARDWARE_DOMAIN,
)
from homeassistant.components.homeassistant_hardware.helpers import (
    async_register_firmware_info_callback,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    OwningIntegration,
)
from homeassistant.components.zha import DOMAIN
from homeassistant.components.zha.homeassistant_hardware import (
    async_update_device_path,
    get_firmware_info,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_get_firmware_info_normal(hass: HomeAssistant) -> None:
    """Test `get_firmware_info`."""

    zha = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data={
            "device": {
                "path": "/dev/ttyUSB1",
                "baudrate": 115200,
                "flow_control": None,
            },
            "radio_type": "ezsp",
        },
        version=5,
    )
    zha.add_to_hass(hass)
    zha.mock_state(hass, ConfigEntryState.LOADED)

    # With ZHA running
    with patch(
        "homeassistant.components.zha.homeassistant_hardware.get_zha_gateway"
    ) as mock_get_zha_gateway:
        mock_get_zha_gateway.return_value.state.node_info.version = "1.2.3.4"
        fw_info_running = get_firmware_info(hass, zha)

    assert fw_info_running == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.EZSP,
        firmware_version="1.2.3.4",
        source="zha",
        owners=[OwningIntegration(config_entry_id=zha.entry_id)],
    )
    assert await fw_info_running.is_running(hass) is True

    # With ZHA not running
    zha.mock_state(hass, ConfigEntryState.NOT_LOADED)
    fw_info_not_running = get_firmware_info(hass, zha)

    assert fw_info_not_running == FirmwareInfo(
        device="/dev/ttyUSB1",
        firmware_type=ApplicationType.EZSP,
        firmware_version=None,
        source="zha",
        owners=[OwningIntegration(config_entry_id=zha.entry_id)],
    )
    assert await fw_info_not_running.is_running(hass) is False


@pytest.mark.parametrize(
    "data",
    [
        # Missing data
        {},
        # Bad radio type
        {"device": {"path": "/dev/ttyUSB1"}, "radio_type": "znp"},
    ],
)
async def test_get_firmware_info_errors(
    hass: HomeAssistant, data: dict[str, str | int | None]
) -> None:
    """Test `get_firmware_info` with config entry data format errors."""
    zha = MockConfigEntry(
        domain=DOMAIN,
        unique_id="some_unique_id",
        data=data,
        version=5,
    )
    zha.add_to_hass(hass)

    assert (get_firmware_info(hass, zha)) is None


@pytest.mark.parametrize(
    ("state", "reloads"),
    [
        (ConfigEntryState.LOADED, 1),
        (ConfigEntryState.SETUP_RETRY, 1),
        (ConfigEntryState.NOT_LOADED, 0),
    ],
)
async def test_async_update_device_path(
    hass: HomeAssistant, state: ConfigEntryState, reloads: int
) -> None:
    """Following the radio rewrites only the path and reloads an entry that is up."""
    zha = MockConfigEntry(
        domain=DOMAIN,
        unique_id="epid=0011223344556677",
        data={
            "device": {
                "path": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_10B41DE58F10-if00",
                "baudrate": 115200,
                "flow_control": "hardware",
            },
            "radio_type": "ezsp",
        },
        version=5,
    )
    zha.add_to_hass(hass)
    zha.mock_state(hass, state)

    new_path = "esphome-hass://esphome/entry?port_name=USB&usb_serial=10B41DE58F10"
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        await async_update_device_path(hass, zha, new_path)

    assert zha.data["device"] == {
        "path": new_path,
        "baudrate": 115200,
        "flow_control": "hardware",
    }
    assert mock_reload.mock_calls == [call(zha.entry_id)] * reloads

    # The same path again is not a move
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        await async_update_device_path(hass, zha, new_path)
    assert len(mock_reload.mock_calls) == 0


async def test_hardware_firmware_info_provider_notification(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect: ControllerApplication,
) -> None:
    """Test that the ZHA gateway provides hardware and firmware information."""
    config_entry.add_to_hass(hass)

    await async_setup_component(hass, HOMEASSISTANT_HARDWARE_DOMAIN, {})

    callback = MagicMock()
    async_register_firmware_info_callback(hass, "/dev/ttyUSB0", callback)

    await hass.config_entries.async_setup(config_entry.entry_id)

    callback.assert_called_once_with(
        FirmwareInfo(
            device="/dev/ttyUSB0",
            firmware_type=ApplicationType.EZSP,
            firmware_version="7.1.4.0 build 389",
            source="zha",
            owners=[OwningIntegration(config_entry_id=config_entry.entry_id)],
        )
    )
