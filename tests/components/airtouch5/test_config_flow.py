"""Test the Airtouch 5 config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.airtouch5.config_flow import AirTouch5ConfigFlow
from homeassistant.components.airtouch5.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import AirtouchDevice

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_success(
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


async def test_cannot_connect(
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
    assert result3["errors"] == {"base": "device_not_found"}
