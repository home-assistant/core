"""Tests for the ATEN PE initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

from atenpdu import AtenPEError

from homeassistant.components.aten_pe.const import DOMAIN
from homeassistant.components.aten_pe.util import create_aten_pe_device
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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


async def test_setup_unload_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
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
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED
        mock_device.close.assert_called_once()


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test handling AtenPEError during setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.100",
            "port": "161",
            "community": "private",
            "username": "administrator",
        },
    )
    entry.add_to_hass(hass)

    mock_device = MagicMock()
    mock_device.initialize = AsyncMock(side_effect=AtenPEError("SNMP Failure"))
    mock_device.close = MagicMock()

    with patch(
        "homeassistant.components.aten_pe.create_aten_pe_device",
        return_value=mock_device,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
        mock_device.close.assert_called_once()


def test_create_aten_pe_device() -> None:
    """Test create_aten_pe_device helper function."""
    with (
        patch("homeassistant.components.aten_pe.util.AtenPE") as mock_aten_pe_class,
        patch(
            "homeassistant.components.aten_pe.util.MibViewControllerManager"
        ) as mock_mvc_manager,
    ):
        mock_device = MagicMock()
        mock_aten_pe_class.return_value = mock_device

        mock_mvc = MagicMock()
        mock_mvc_manager.get_mib_view_controller.return_value = mock_mvc

        dev = create_aten_pe_device(
            "192.168.1.100",
            "161",
            "private",
            "administrator",
            None,
            None,
        )

        assert dev is mock_device
        mock_aten_pe_class.assert_called_once_with(
            node="192.168.1.100",
            serv="161",
            community="private",
            username="administrator",
            authkey=None,
            privkey=None,
        )
        mock_mvc_manager.get_mib_view_controller.assert_called_once_with(
            mock_device._snmp_engine.cache
        )
        mock_mvc.mibBuilder.load_modules.assert_called_once()
