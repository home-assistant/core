"""Test the LoRaWAN config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.lorawan.const import DOMAIN
from homeassistant.components.lorawan.helpers.exceptions import (
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.lorawan.models import Device
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


LIST_DEVICE_EUIS_TWO_DEVICES = [
    Device("0011223344556677", "test-device-1"),
    Device("1122334455667788", "test-device-2"),
]

FORM_DATA = {
    "application": "TEST-APPLICATION",
    "api_key": "TEST API KEY",
    "url": "https://TEST-URL",
    "device_eui": "0011223344556677",
    "manufacturer": "browan",
    "model": "tbms100",
}


@patch(
    "homeassistant.components.lorawan.network_servers.ttn.TTN.list_device_euis",
    return_value=LIST_DEVICE_EUIS_TWO_DEVICES,
)
async def test_form(
    mock_list_device_euis: AsyncMock,
    mock_setup_entry: AsyncMock,
    hass: HomeAssistant,
) -> None:
    """Test we get the form."""
    form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert form_result["type"] == FlowResultType.FORM
    assert form_result["errors"] == {}

    validation_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        FORM_DATA,
    )
    await hass.async_block_till_done()
    assert validation_result["type"] == FlowResultType.CREATE_ENTRY
    assert validation_result["title"] == "test-device-1"
    assert validation_result["data"] == FORM_DATA
    assert validation_result["context"] == {
        "source": "user",
        "unique_id": "0011223344556677",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@patch(
    "homeassistant.components.lorawan.network_servers.ttn.TTN.list_device_euis",
    side_effect=InvalidAuth,
)
async def test_form_invalid_auth(
    mock_list_device_euis: AsyncMock, hass: HomeAssistant
) -> None:
    """Test we handle invalid auth."""

    form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    validation_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        FORM_DATA,
    )

    assert validation_result["type"] == FlowResultType.FORM
    assert validation_result["errors"] == {"base": "invalid_auth"}


@patch(
    "homeassistant.components.lorawan.network_servers.ttn.TTN.list_device_euis",
    side_effect=CannotConnect(500),
)
async def test_form_cannot_connect(
    mock_list_device_euis: AsyncMock, hass: HomeAssistant
) -> None:
    """Test we handle cannot connect error."""
    form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    validation_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        FORM_DATA,
    )

    assert validation_result["type"] == FlowResultType.FORM
    assert validation_result["errors"] == {"base": "cannot_connect: 500"}
