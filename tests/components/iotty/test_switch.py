"""Unit tests for the SWITCH component."""

from unittest.mock import AsyncMock

from iottycloud.lightswitch import LightSwitch
from iottycloud.verbs import LS_DEVICE_TYPE_UID
import pytest

from homeassistant.components.iotty.api import IottyProxy
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.switch import IottyLightSwitch, async_setup_entry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

test_ls = [
    LightSwitch(
        "TestDevice0", "TEST_SERIAL_0", LS_DEVICE_TYPE_UID, "[TEST] Device Name 0"
    )
]


async def test_creation_ok(mock_iotty: IottyProxy) -> None:
    """Create a hass Switch from existing LS."""

    sut = IottyLightSwitch(mock_iotty, test_ls[0])
    assert sut is not None


async def test_device_id_ok(mock_iotty: IottyProxy) -> None:
    """Retrieve the nested device_id."""
    sut = IottyLightSwitch(mock_iotty, test_ls[0])

    assert sut.device_id == test_ls[0].device_id


async def test_name_ok(mock_iotty: IottyProxy) -> None:
    """Retrieve the nested device name."""
    sut = IottyLightSwitch(mock_iotty, test_ls[0])

    assert sut.name == test_ls[0].name


async def test_is_on_ok(mock_iotty: IottyProxy) -> None:
    """Retrieve the nested status."""
    sut = IottyLightSwitch(mock_iotty, test_ls[0])

    test_ls[0].is_on = True

    assert sut.is_on == test_ls[0].is_on


async def test_turn_on_ok(
    hass: HomeAssistant, mock_iotty: IottyProxy, mock_iotty_command_fn
) -> None:
    """Issue a turnon command."""
    mock_iotty.command = AsyncMock()
    sut = IottyLightSwitch(mock_iotty, test_ls[0])
    await sut.async_turn_on()
    await hass.async_block_till_done()

    mock_iotty.command.assert_called_once_with(
        test_ls[0].device_id, test_ls[0].cmd_turn_on()
    )


async def test_turn_off_ok(
    hass: HomeAssistant, mock_iotty: IottyProxy, mock_iotty_command_fn
) -> None:
    """Issue a turnoff command."""
    mock_iotty.command = AsyncMock()
    sut = IottyLightSwitch(mock_iotty, test_ls[0])
    await sut.async_turn_off()
    await hass.async_block_till_done()

    mock_iotty.command.assert_called_once_with(
        test_ls[0].device_id, test_ls[0].cmd_turn_off()
    )


async def test_creation_wrongdomaindata_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_iotty: IottyProxy
) -> None:
    """Create a hass Switch with empty or wrong DOMAIN data."""

    with pytest.raises(KeyError):
        await async_setup_entry(hass, mock_config_entry, None)

    hass.data.setdefault(DOMAIN, {})
    with pytest.raises(KeyError):
        await async_setup_entry(hass, mock_config_entry, None)
