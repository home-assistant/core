"""Test the acaia config flow."""

from unittest.mock import AsyncMock

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
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_IS_NEW_STYLE_SCALE: True,
    }
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "acaia"
    assert result2["data"] == user_input


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
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

    user_input = {
        CONF_IS_NEW_STYLE_SCALE: False,
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_MAC: service_info.address,
        CONF_NAME: service_info.name,
        CONF_IS_NEW_STYLE_SCALE: False,
    }


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Testing reconfgure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    user_input = {
        CONF_MAC: "aa:bb:cc:dd:ee:gg",
        CONF_IS_NEW_STYLE_SCALE: False,
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        **mock_config_entry.data,
        **user_input,
    }
