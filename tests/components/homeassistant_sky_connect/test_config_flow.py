"""Test the Home Assistant Sky Connect config flow."""
import copy
from unittest.mock import patch

from homeassistant.components import homeassistant_sky_connect, usb
from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USB_DATA = usb.UsbServiceInfo(
    device="bla_device",
    vid="bla_vid",
    pid="bla_pid",
    serial_number="bla_serial_number",
    manufacturer="bla_manufacturer",
    description="bla_description",
)


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=USB_DATA
        )

    expected_data = {
        "device": USB_DATA.device,
        "vid": USB_DATA.vid,
        "pid": USB_DATA.pid,
        "serial_number": USB_DATA.serial_number,
        "manufacturer": USB_DATA.manufacturer,
        "description": USB_DATA.description,
    }

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant Sky Connect"
    assert result["data"] == expected_data
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == expected_data
    assert config_entry.options == {}
    assert config_entry.title == "Home Assistant Sky Connect"
    assert (
        config_entry.unique_id
        == f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}"
    )


async def test_config_flow_unique_id(hass: HomeAssistant) -> None:
    """Test only a single entry is allowed for a dongle."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=USB_DATA
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_setup_entry.assert_not_called()


async def test_config_flow_multiple_entries(hass: HomeAssistant) -> None:
    """Test multiple entries are allowed."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    usb_data = copy.copy(USB_DATA)
    usb_data.serial_number = "bla_serial_number_2"

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_config_flow_update_device(hass: HomeAssistant) -> None:
    """Test updating device path."""
    # Setup an existing config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
        unique_id=f"{USB_DATA.vid}:{USB_DATA.pid}_{USB_DATA.serial_number}_{USB_DATA.manufacturer}_{USB_DATA.description}",
    )
    config_entry.add_to_hass(hass)

    usb_data = copy.copy(USB_DATA)
    usb_data.device = "bla_device_2"

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert len(mock_setup_entry.mock_calls) == 1

    with patch(
        "homeassistant.components.homeassistant_sky_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.homeassistant_sky_connect.async_unload_entry",
        wraps=homeassistant_sky_connect.async_unload_entry,
    ) as mock_unload_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "usb"}, data=usb_data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_unload_entry.mock_calls) == 1
