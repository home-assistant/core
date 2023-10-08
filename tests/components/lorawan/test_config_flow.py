"""Test the LoRaWAN config flow."""
import logging
from unittest.mock import AsyncMock, patch

from pyliblorawan.helpers.exceptions import CannotConnect, InvalidAuth
from pyliblorawan.models import Device
import pytest

from homeassistant import config_entries
from homeassistant.components.lorawan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


LIST_DEVICE_EUIS_TWO_DEVICES = [
    Device("AA11223344556677", "test-device-1"),
    Device("1122334455667788", "test-device-2"),
]

FORM_DATA = {
    "application": "TEST-APPLICATION",
    "api_key": "TEST API KEY",
    "url": "https://TEST-URL",
    "device_eui": "aa11223344556677",
    "manufacturer": "browan",
    "model": "tbms100",
}


@patch(
    "pyliblorawan.network_servers.ttn.TTN.list_device_euis",
    return_value=LIST_DEVICE_EUIS_TWO_DEVICES,
)
async def test_form(
    mock_list_device_euis: AsyncMock,
    mock_setup_entry: AsyncMock,
    hass: HomeAssistant,
    set_caplog_debug: pytest.LogCaptureFixture,
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
        "unique_id": "AA11223344556677",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    assert set_caplog_debug.record_tuples == []


@patch(
    "pyliblorawan.network_servers.ttn.TTN.list_device_euis",
    side_effect=InvalidAuth,
)
async def test_form_invalid_auth(
    mock_list_device_euis: AsyncMock,
    hass: HomeAssistant,
    set_caplog_debug: pytest.LogCaptureFixture,
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

    assert set_caplog_debug.record_tuples == []


@patch(
    "pyliblorawan.network_servers.ttn.TTN.list_device_euis",
    side_effect=CannotConnect(500),
)
async def test_form_cannot_connect(
    mock_list_device_euis: AsyncMock,
    hass: HomeAssistant,
    set_caplog_debug: pytest.LogCaptureFixture,
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

    assert set_caplog_debug.record_tuples == []


@patch(
    "pyliblorawan.network_servers.ttn.TTN.list_device_euis",
    side_effect=ValueError,
)
async def test_generic_exception(
    mock_list_device_euis: AsyncMock,
    hass: HomeAssistant,
    set_caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test that we handle unexpected exceptions."""
    form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    validation_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        FORM_DATA,
    )

    assert validation_result["type"] == FlowResultType.FORM
    assert validation_result["errors"] == {"base": "unknown"}

    assert set_caplog_debug.record_tuples == [
        (
            "homeassistant.components.lorawan.config_flow",
            logging.ERROR,
            "Unexpected exception",
        )
    ]


@patch(
    "pyliblorawan.network_servers.ttn.TTN.list_device_euis",
    return_value=LIST_DEVICE_EUIS_TWO_DEVICES,
)
async def test_device_not_found(
    mock_list_device_euis: AsyncMock,
    hass: HomeAssistant,
    set_caplog_debug: pytest.LogCaptureFixture,
) -> None:
    """Test the exception when a device is not found."""
    FORM_DATA["device_eui"] = "00112233445566ff"

    form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    validation_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        FORM_DATA,
    )

    assert validation_result["type"] == FlowResultType.FORM
    assert validation_result["errors"] == {
        "base": 'Device "00112233445566FF" is not in the application'
    }

    assert set_caplog_debug.record_tuples == []


@pytest.mark.parametrize(
    "device_eui",
    [
        "aa1122334455667",
        "aa112233445566777",
        "ga11223344556677",
        "Ga11223344556677",
        "-a11223344556677",
        "*a11223344556677",
        ":a11223344556677",
        "+a11223344556677",
    ],
)
async def test_invalid_device_eui(
    hass: HomeAssistant, set_caplog_debug: pytest.LogCaptureFixture, device_eui: str
) -> None:
    """Test a set of invalid device EUIs."""
    form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    FORM_DATA["device_eui"] = device_eui

    validation_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        FORM_DATA,
    )

    assert validation_result["type"] == FlowResultType.FORM
    assert validation_result["errors"] == {
        "base": f'Invalid device EUI "{device_eui}". It should match "^[0-9a-fA-F]{{16}}$"'
    }

    assert set_caplog_debug.record_tuples == []
