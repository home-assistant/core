"""Test the config flow for the Probe Plus."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.probe_plus.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

service_info = BluetoothServiceInfo(
    name="FM210 aa:bb:cc:dd:ee:ff",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-63,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
)


@pytest.fixture
def mock_discovered_service_info() -> Generator[AsyncMock]:
    """Override getting Bluetooth service info."""
    with patch(
        "homeassistant.components.probe_plus.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ) as mock_discovered_service_info:
        yield mock_discovered_service_info


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovered_service_info: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovered_service_info: AsyncMock,
) -> None:
    """Test we can discover a device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    user_input = {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_ADDRESS: service_info.address,
    }


async def test_already_configured_bluetooth_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure configure device is not discovered again."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_bluetooth_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovered_service_info: AsyncMock,
) -> None:
    """Test flow aborts on unsupported device."""
    mock_discovered_service_info.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
