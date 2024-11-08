"""Test the acaia config flow."""

from unittest.mock import AsyncMock

from pyacaia_async.exceptions import AcaiaDeviceNotFound, AcaiaError, AcaiaUnknownDevice
import pytest

from homeassistant.components.acaia.const import CONF_IS_NEW_STYLE_SCALE, DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verify: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "acaia"
    assert result2["data"] == {
        **user_input,
        CONF_IS_NEW_STYLE_SCALE: True,
    }


async def test_bluetooth_discovery_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verify: AsyncMock,
) -> None:
    """Test we can discover a device."""

    service_info = BluetoothServiceInfo(
        name="LUNAR_123456",
        address="aa:bb:cc:dd:ee:ff",
        rssi=-63,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_MAC: service_info.address,
        CONF_NAME: service_info.name,
        CONF_IS_NEW_STYLE_SCALE: True,
    }


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verify: AsyncMock,
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
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AcaiaDeviceNotFound("Error"), "device_not_found"),
        (AcaiaError, "unknown"),
    ],
)
async def test_recoverable_config_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verify: AsyncMock,
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
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    # recover
    mock_verify.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_unsupported_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verify: AsyncMock,
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
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unsupported_device"
