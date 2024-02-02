"""Test the Fujitsu HVAC (based on Ayla IOT) config flow."""
from unittest.mock import AsyncMock, patch

from ayla_iot_unofficial import AylaAuthError
from ayla_iot_unofficial.fujitsu_hvac import FujitsuHVAC

from homeassistant import config_entries
from homeassistant.components.fujitsu_hvac.const import (
    AYLA_APP_ID,
    AYLA_APP_SECRET,
    CONF_DEVICE,
    CONF_EUROPE,
    DOMAIN,
    NO_DEVICES_ERROR,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

TEST_DEVICE_NAME = "Test device"
TEST_DEVICE_SERIAL = "testserial"
TEST_USERNAME = "test-username"
TEST_PASSWORD = "test-password"


async def _initial_step(hass: HomeAssistant, apimock: AsyncMock) -> FlowResult:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fujitsu_hvac.config_flow.new_ayla_api",
        return_value=apimock,
    ) as mock_new_api:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_EUROPE: False,
            },
        )
        await hass.async_block_till_done()

        mock_new_api.assert_called_once_with(
            TEST_USERNAME, TEST_PASSWORD, AYLA_APP_ID, AYLA_APP_SECRET, europe=False
        )
        apimock.async_sign_in.assert_called_once()

    return result


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    apimock = AsyncMock()
    result = await _initial_step(hass, apimock)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == NO_DEVICES_ERROR


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    apimock = AsyncMock()
    apimock.async_sign_in.side_effect = AylaAuthError

    result = await _initial_step(hass, apimock)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    apimock = AsyncMock()
    with patch(
        "homeassistant.components.fujitsu_hvac.config_flow.new_ayla_api",
        return_value=apimock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_EUROPE: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == NO_DEVICES_ERROR


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    apimock = AsyncMock()
    apimock.async_sign_in.side_effect = TimeoutError

    result = await _initial_step(hass, apimock)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    apimock = AsyncMock()
    with patch(
        "homeassistant.components.fujitsu_hvac.config_flow.new_ayla_api",
        return_value=apimock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_EUROPE: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == NO_DEVICES_ERROR


async def test_form_one_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that we get the device selection form and that it creates an entry when submitted."""
    apimock = AsyncMock()
    devicemock = AsyncMock(spec=FujitsuHVAC)
    devicemock.device_name = TEST_DEVICE_NAME
    devicemock.device_serial_number = TEST_DEVICE_SERIAL
    apimock.async_get_devices.return_value = [devicemock]

    result = await _initial_step(hass, apimock)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_device"
    assert result["data_schema"]({CONF_DEVICE: TEST_DEVICE_SERIAL})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: TEST_DEVICE_SERIAL}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["data"] == {
        CONF_DEVICE: TEST_DEVICE_SERIAL,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_EUROPE: False,
    }
