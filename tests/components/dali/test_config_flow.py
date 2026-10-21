"""Test the Tridonic DALI config flow."""

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from dali.driver.serial import DriverLubaRs232
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.dali.const import CONF_BUS_POWER, DOMAIN
from homeassistant.components.usb import (
    SerialDevice,
    USBDevice,
    usb_service_info_from_device,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import SerialPortSelector
from homeassistant.helpers.service_info.usb import UsbServiceInfo


def _mock_driver(
    driver: MagicMock,
    *,
    connect_side_effect: type[Exception] | None = None,
    has_bus_power_supply: bool = False,
    descriptor_unavailable: bool = False,
) -> None:
    """Configure a patched DriverLubaRs232 mock for the config flow."""
    driver.return_value.connect = AsyncMock(side_effect=connect_side_effect)
    driver.return_value._transport = MagicMock()
    descriptor = (
        None
        if descriptor_unavailable
        else SimpleNamespace(has_bus_power_supply=has_bus_power_supply)
    )
    driver.return_value.query_device_descriptor = AsyncMock(return_value=descriptor)


DISCOVERY_INFO = UsbServiceInfo(
    device="/dev/ttyACM0",
    vid="0403",
    pid="6015",
    serial_number="123456",
    manufacturer="Lunatone",
    description="USB-DALI2",
)

USB_PORT = USBDevice(
    device="/dev/ttyACM0",
    vid="0403",
    pid="6015",
    serial_number="123456",
    manufacturer="Lunatone",
    description="USB-DALI2",
)

BY_ID_PATH = "/dev/serial/by-id/usb-Lunatone_USB-DALI2"
PORT_LABEL = "Lunatone USB-DALI2 (123456)"


def test_probe_uses_a_supported_connect_argument() -> None:
    """Guard against pinning a python-dali that rejects the read-only probe.

    ``_async_probe`` connects with ``apply_settings=False``; a pinned release
    without that argument would raise ``TypeError`` during setup and discovery.
    """
    assert "apply_settings" in inspect.signature(DriverLubaRs232.connect).parameters


async def test_usb_discovery(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test USB discovery creates an entry for the interface."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEVICE: "/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        CONF_BUS_POWER: False,
    }
    assert result["result"].unique_id
    assert len(mock_setup_entry.mock_calls) == 1
    driver.return_value.connect.assert_awaited_once_with(apply_settings=False)
    driver.return_value._transport.close.assert_called_once_with()


async def test_usb_discovery_cannot_connect(hass: HomeAssistant) -> None:
    """Test USB discovery aborts when the interface cannot be opened."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, connect_side_effect=OSError)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    driver.return_value._transport.close.assert_called_once_with()


async def test_usb_discovery_descriptor_unavailable(hass: HomeAssistant) -> None:
    """Test USB discovery aborts when the interface descriptor cannot be read."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, descriptor_unavailable=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    driver.return_value._transport.close.assert_called_once_with()


async def test_user_flow_descriptor_unavailable(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the manual flow recovers when the descriptor is unreadable then readable."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[USB_PORT],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, descriptor_unavailable=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        driver.return_value.query_device_descriptor = AsyncMock(
            return_value=SimpleNamespace(has_bus_power_supply=False)
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_usb_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test USB rediscovery updates the configured interface path."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=usb_unique_id_from_service_info(DISCOVERY_INFO),
        data={CONF_DEVICE: "/dev/serial/by-id/usb-Lunatone_USB-DALI2-old"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
        return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_DEVICE] == "/dev/serial/by-id/usb-Lunatone_USB-DALI2"


async def test_user_flow_selected_port_removed(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a selected serial port disappearing before submission is handled."""
    other_port = SerialDevice(
        device="/dev/ttyUSB1",
        serial_number=None,
        manufacturer=None,
        description=None,
    )
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            side_effect=[[USB_PORT], [other_port], [other_port]],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/ttyUSB1",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        assert result["step_id"] == "user"

        # The originally selected port is gone on submission.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        # Selecting a port that is still present recovers and creates the entry.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyUSB1"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE] == "/dev/ttyUSB1"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_two_manual_flows_same_port_abort_duplicate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a second manual flow for the same port aborts instead of duplicating."""
    serial_port = SerialDevice(
        device="/dev/ttyUSB0",
        serial_number=None,
        manufacturer=None,
        description=None,
    )
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[serial_port],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/ttyUSB0",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, has_bus_power_supply=True)

        # Two flows for the same port both reach the bus-power step before either
        # has created an entry.
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], {CONF_DEVICE: "/dev/ttyUSB0"}
        )
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {CONF_DEVICE: "/dev/ttyUSB0"}
        )
        assert first["step_id"] == "bus_power"
        assert second["step_id"] == "bus_power"

        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], {CONF_BUS_POWER: False}
        )
        assert first["type"] is FlowResultType.CREATE_ENTRY
        assert first["result"].unique_id is None

        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {CONF_BUS_POWER: False}
        )

    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the manual flow selects a serial port and creates an entry."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[USB_PORT],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEVICE: "/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        CONF_BUS_POWER: False,
    }
    assert result["result"].unique_id == usb_unique_id_from_service_info(
        usb_service_info_from_device(USB_PORT)
    )
    assert len(mock_setup_entry.mock_calls) == 1
    driver.return_value._transport.close.assert_called_once_with()


async def test_user_flow_uses_serial_port_selector(hass: HomeAssistant) -> None:
    """Test the manual flow offers a serial port selector.

    The selector is what lists DALI in the ESPHome serial-proxy setup wizard; a
    plain enum dropdown would still work but keep DALI out of that wizard.
    """
    with patch(
        "homeassistant.components.dali.config_flow.async_scan_serial_ports",
        return_value=[USB_PORT],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert isinstance(result["data_schema"].schema[CONF_DEVICE], SerialPortSelector)


async def test_user_flow_non_usb_port(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the manual flow accepts a plain serial port without a unique ID."""
    serial_port = SerialDevice(
        device="/dev/ttyUSB0",
        serial_number=None,
        manufacturer=None,
        description=None,
    )
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[serial_port],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/ttyUSB0",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICE: "/dev/ttyUSB0", CONF_BUS_POWER: False}
    assert result["result"].unique_id is None
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_no_serial_ports(hass: HomeAssistant) -> None:
    """Test the manual flow aborts when no serial ports are available."""
    with patch(
        "homeassistant.components.dali.config_flow.async_scan_serial_ports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_ports"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the manual flow shows an error and recovers when the port fails."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[USB_PORT],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, connect_side_effect=OSError)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

        driver.return_value.connect = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_enable_bus_power(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the manual flow offers to power the bus when the interface can."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[USB_PORT],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, has_bus_power_supply=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bus_power"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BUS_POWER: True}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEVICE: "/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        CONF_BUS_POWER: True,
    }
    assert result["result"].unique_id == usb_unique_id_from_service_info(
        usb_service_info_from_device(USB_PORT)
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_usb_discovery_enable_bus_power(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test USB discovery offers to power the bus when the interface can."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, has_bus_power_supply=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USB},
            data=DISCOVERY_INFO,
        )

        assert result["step_id"] == "usb_confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bus_power"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BUS_POWER: True}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_DEVICE: "/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        CONF_BUS_POWER: True,
    }
    assert result["result"].unique_id == usb_unique_id_from_service_info(DISCOVERY_INFO)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_decline_bus_power(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the bus-power offer can be declined, storing bus_power off."""
    with (
        patch(
            "homeassistant.components.dali.config_flow.async_scan_serial_ports",
            return_value=[USB_PORT],
        ),
        patch(
            "homeassistant.components.dali.config_flow.usb.get_serial_by_id",
            return_value="/dev/serial/by-id/usb-Lunatone_USB-DALI2",
        ),
        patch("homeassistant.components.dali.config_flow.DriverLubaRs232") as driver,
    ):
        _mock_driver(driver, has_bus_power_supply=True)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bus_power"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BUS_POWER: False}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BUS_POWER] is False
    assert result["result"].unique_id == usb_unique_id_from_service_info(
        usb_service_info_from_device(USB_PORT)
    )
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test the manual flow aborts when the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=usb_unique_id_from_service_info(
            usb_service_info_from_device(USB_PORT)
        ),
        data={CONF_DEVICE: "/dev/ttyACM0"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dali.config_flow.async_scan_serial_ports",
        return_value=[USB_PORT],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE: "/dev/ttyACM0"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
