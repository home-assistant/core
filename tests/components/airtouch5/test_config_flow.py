"""Test the Airtouch 5 config flow."""

import contextlib
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.airtouch5.config_flow import AirTouch5ConfigFlow
from homeassistant.components.airtouch5.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import AirtouchDevice

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_manual_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""

    host = "1.1.1.1"

    # Create a fake device to return from the mock
    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip=host,
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=fake_device,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": "manual"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "manual"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": host,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"]["host"] == host

    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_connection_exception(
    hass: HomeAssistant, mock_airtouch_discovery: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip="1.1.1.1",
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            side_effect=Exception,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": "manual"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "manual"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_select_success(
    hass: HomeAssistant,
    mock_airtouch_discovery: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle device not found error."""

    # Create a fake device to return from the mock
    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip="1.1.1.1",
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=fake_device,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": fake_device.system_id},
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"]["host"] == fake_device.ip
        assert len(mock_setup_entry.mock_calls) == 1


async def test_select_connection_exception(
    hass: HomeAssistant,
    mock_airtouch_discovery: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle device not found error."""

    # Create a fake device to return from the mock
    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip="1.1.1.1",
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=fake_device,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            return_value=Exception,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": fake_device.system_id},
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"]["host"] == fake_device.ip
        assert len(mock_setup_entry.mock_calls) == 1


async def test_discovery_success() -> None:
    """Test discovery returns devices."""
    flow = AirTouch5ConfigFlow()

    fake_devices = [
        AirtouchDevice(
            system_id="123",
            name="Test",
            ip="1.1.1.1",
            model="AT5",
            console_id="abc",
        )
    ]

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover.return_value = fake_devices
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        devices = await flow._discovery()

    assert devices == fake_devices
    mock_instance.establish_server.assert_awaited_once()
    mock_instance.discover.assert_awaited_once()
    mock_instance.close.assert_awaited_once()


async def test_discovery_exception_returns_empty() -> None:
    """Test discovery handles exceptions and always closes."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.side_effect = Exception("boom")
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        devices = await flow._discovery()

    assert devices == []
    mock_instance.close.assert_awaited_once()


async def test_discovery_always_closes() -> None:
    """Test discovery always closes the connection."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover.side_effect = Exception("fail")
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        await flow._discovery()

    mock_instance.close.assert_awaited_once()


async def test_discover_device_by_ip_success() -> None:
    """Test discover_device_by_ip returns a device."""
    flow = AirTouch5ConfigFlow()

    fake_device = AirtouchDevice(
        system_id="123",
        name="Test",
        ip="1.1.1.1",
        model="AT5",
        console_id="abc",
    )

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover_by_ip.return_value = fake_device
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        device = await flow._discover_device_by_ip("1.1.1.1")

    assert device == fake_device
    mock_instance.establish_server.assert_awaited_once()
    mock_instance.discover_by_ip.assert_awaited_once_with("1.1.1.1")
    mock_instance.close.assert_awaited_once()


async def test_discover_device_by_ip_none() -> None:
    """Test discover_device_by_ip returns None when device is not found."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover_by_ip.return_value = None
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        device = await flow._discover_device_by_ip("1.1.1.1")

    assert device is None
    mock_instance.close.assert_awaited_once()


async def test_discover_device_by_ip_exception_closes() -> None:
    """Test discover_device_by_ip handles exceptions and always closes."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.side_effect = Exception("boom")
    mock_instance.close.return_value = None

    with (
        patch(
            "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
            return_value=mock_instance,
        ),
        contextlib.suppress(Exception),
    ):
        await flow._discover_device_by_ip("1.1.1.1")

    mock_instance.close.assert_awaited_once()
