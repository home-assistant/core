"""Tests for the ATEN PE switch platform."""

from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class Outlet(NamedTuple):
    """Mock outlet named tuple."""

    id: int
    name: str


async def mock_outlets():
    """Mock outlets generator."""
    yield Outlet(1, "Outlet 1")
    yield Outlet(2, "Outlet 2")


def create_mock_device(
    switchable: str = "yes",
    perportreading: str = "yes",
):
    """Create a mock AtenPE device."""
    mock_device = MagicMock()
    mock_device.initialize = AsyncMock()
    mock_device.deviceMAC = AsyncMock(return_value="00:11:22:33:44:55")
    mock_device.deviceName = AsyncMock(return_value="ATEN PDU")
    mock_device.modelName = AsyncMock(return_value="PE6108")
    mock_device.deviceFWversion = AsyncMock(return_value="v1.0.1")
    mock_device.outlets = mock_outlets
    mock_device.displayOutletStatus = AsyncMock(
        side_effect=lambda outlet: "on" if outlet == 1 else "off"
    )
    mock_device.setOutletStatus = AsyncMock()
    mock_device.close = MagicMock()

    # Capabilities mocking
    mock_switchable = MagicMock()
    mock_switchable.getNamedValues.return_value.getName.return_value = switchable

    mock_perport = MagicMock()
    mock_perport.getNamedValues.return_value.getName.return_value = perportreading

    async def get_attribute(key, outlet=None):
        if key == "switchable":
            return mock_switchable
        if key == "perportreading":
            return mock_perport
        return 1.23

    mock_device.getAttribute = AsyncMock(side_effect=get_attribute)
    return mock_device


async def test_aten_pe_switch_setup(hass: HomeAssistant) -> None:
    """Test setting up the ATEN PE switch platform from config entry."""
    entry = MockConfigEntry(
        domain="aten_pe",
        data={
            "host": "192.168.1.100",
            "port": "161",
            "community": "private",
            "username": "administrator",
        },
    )
    entry.add_to_hass(hass)

    mock_device = create_mock_device()

    with patch(
        "homeassistant.components.aten_pe.create_aten_pe_device",
        return_value=mock_device,
    ) as mock_aten_pe:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_aten_pe.assert_called_once_with(
            "192.168.1.100",
            "161",
            "private",
            "administrator",
            None,
            None,
        )

        state_outlet1 = hass.states.get("switch.aten_pdu_outlet_1")
        assert state_outlet1 is not None
        assert state_outlet1.state == STATE_ON

        state_outlet2 = hass.states.get("switch.aten_pdu_outlet_2")
        assert state_outlet2 is not None
        assert state_outlet2.state == STATE_OFF

        # Test turn on / off
        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_off",
            {"entity_id": "switch.aten_pdu_outlet_1"},
            blocking=True,
        )
        mock_device.setOutletStatus.assert_called_with(1, "off")

        await hass.services.async_call(
            SWITCH_DOMAIN,
            "turn_on",
            {"entity_id": "switch.aten_pdu_outlet_2"},
            blocking=True,
        )
        mock_device.setOutletStatus.assert_called_with(2, "on")


async def test_aten_pe_not_switchable(hass: HomeAssistant) -> None:
    """Test setting up when device is not switchable."""
    entry = MockConfigEntry(
        domain="aten_pe",
        data={
            "host": "192.168.1.100",
            "port": "161",
            "community": "private",
            "username": "administrator",
        },
    )
    entry.add_to_hass(hass)

    mock_device = create_mock_device(switchable="no")

    with patch(
        "homeassistant.components.aten_pe.create_aten_pe_device",
        return_value=mock_device,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state_outlet1 = hass.states.get("switch.aten_pdu_outlet_1")
        assert state_outlet1 is None
