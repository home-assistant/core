"""Test the acaia config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError, AcaiaUnknownDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.acaia.const import (
    CONF_IDLE_TIMEOUT,
    CONF_IS_NEW_STYLE_SCALE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

service_info = BluetoothServiceInfo(
    name="LUNAR-DDEEFF",
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
        "homeassistant.components.acaia.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ) as mock_discovered_service_info:
        yield mock_discovered_service_info


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(
    hass: HomeAssistant, mock_verify: AsyncMock, mock_discovered_service_info: AsyncMock
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
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "LUNAR-DDEEFF"
    assert result2["data"] == {
        **user_input,
        CONF_IS_NEW_STYLE_SCALE: True,
    }
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_discovery(hass: HomeAssistant, mock_verify: AsyncMock) -> None:
    """Test we can discover a device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == service_info.name
    assert result2["data"] == {
        CONF_ADDRESS: service_info.address,
        CONF_IS_NEW_STYLE_SCALE: True,
    }
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AcaiaDeviceNotFound("Error"), "device_not_found"),
        (AcaiaError, "unknown"),
        (AcaiaUnknownDevice, "unsupported_device"),
    ],
)
async def test_bluetooth_discovery_errors(
    hass: HomeAssistant,
    mock_verify: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test abortions of Bluetooth discovery."""
    mock_verify.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verify: AsyncMock,
    mock_discovered_service_info: AsyncMock,
) -> None:
    """Ensure we can't add the same device twice."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


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


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AcaiaDeviceNotFound("Error"), "device_not_found"),
        (AcaiaError, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_recoverable_config_flow_errors(
    hass: HomeAssistant,
    mock_verify: AsyncMock,
    mock_discovered_service_info: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test recoverable errors."""
    mock_verify.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    # recover
    mock_verify.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_unsupported_device(
    hass: HomeAssistant, mock_verify: AsyncMock, mock_discovered_service_info: AsyncMock
) -> None:
    """Test flow aborts on unsupported device."""
    mock_verify.side_effect = AcaiaUnknownDevice
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unsupported_device"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_no_bluetooth_devices(
    hass: HomeAssistant, mock_discovered_service_info: AsyncMock
) -> None:
    """Test flow aborts on unsupported device."""
    mock_discovered_service_info.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_options_flow_defaults_and_reload(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the options flow stores the options and reloads the entry."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {CONF_IDLE_TIMEOUT: 0}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_IDLE_TIMEOUT: 15.0},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {CONF_IDLE_TIMEOUT: 15}
    assert init_integration.state is ConfigEntryState.LOADED
    # The reload released the connection of the previous coordinator.
    mock_scale.disconnect.assert_called_once()


@pytest.mark.parametrize(
    "user_input",
    [
        {CONF_IDLE_TIMEOUT: -1},
        {CONF_IDLE_TIMEOUT: 121},
    ],
)
async def test_options_flow_rejects_out_of_range_timeout(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    user_input: dict[str, Any],
) -> None:
    """Test the idle timeout has to be in range."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=user_input
        )
