"""Test the hausbus config flow."""

from unittest.mock import AsyncMock, Mock, patch

from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.HomeServer import HomeServer
import pytest

from homeassistant import config_entries
from homeassistant.components.hausbus.config_flow import ConfigFlow
from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .helpers import create_configuration

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form_user_timeout(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form but not device is found, so we get a timeout."""
    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.config_flow.HomeServer",
        return_value=mock_home_server,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await create_configuration(hass, result)
    assert result2["type"] == FlowResultType.SHOW_PROGRESS
    assert result2["step_id"] == "wait_for_device"

    await hass.async_block_till_done()

    result3 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "search_timeout"

    # try searching for a device a second time
    result4 = await create_configuration(hass, result3)
    assert result4["type"] == FlowResultType.SHOW_PROGRESS
    assert result4["step_id"] == "wait_for_device"

    await hass.async_block_till_done()

    result5 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result5["type"] is FlowResultType.FORM
    assert result5["step_id"] == "search_timeout"


async def test_form_user_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form and a hausbus device is found."""

    def init_patch(self):
        self._found_device = True
        self._search_task = None
        self.home_server = mock_home_server
        self.home_server.addBusEventListener(self)

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with (
        patch(
            "homeassistant.components.hausbus.config_flow.HomeServer",
            return_value=mock_home_server,
        ),
        patch.object(ConfigFlow, "__init__", init_patch),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await create_configuration(hass, result)

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Haus-Bus"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_own_bus_data_received(hass: HomeAssistant) -> None:
    """Test handling of own bus data."""
    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.config_flow.HomeServer",
        return_value=mock_home_server,
    ):
        config_flow = ConfigFlow()

    sender = 0x270E0000  # own object id
    receiver = 0x270E0000  # own object id
    data = {}
    busDataMessage = BusDataMessage(sender, receiver, data)
    config_flow.busDataReceived(busDataMessage)

    # device found flag should still be set to False
    assert not config_flow._found_device


async def test_module_id_received(hass: HomeAssistant) -> None:
    """Test handling of own bus data."""
    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.config_flow.HomeServer",
        return_value=mock_home_server,
    ):
        config_flow = ConfigFlow()

    module = ModuleId("module", 0, 1, 0, EFirmwareId.ESP32)

    sender = 66051  # = 0x00 01 02 03, with class_id = 0x02 and instance_id = 0x03
    receiver = 0x270E0000  # own object id
    data = module
    busDataMessage = BusDataMessage(sender, receiver, data)
    config_flow.busDataReceived(busDataMessage)

    # device found flag should be set to True
    assert config_flow._found_device
