"""Test the air-Q config flow."""
from unittest.mock import patch

from aioairq import DeviceInfo, InvalidAuth, InvalidInput
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant import config_entries
from homeassistant.components.airq.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_DATA = {
    CONF_IP_ADDRESS: "192.168.0.0",
    CONF_PASSWORD: "password",
}
TEST_REAUTH_DATA = {
    CONF_PASSWORD: "password",
}
TEST_DEVICE_INFO = DeviceInfo(
    id="id",
    name="name",
    model="model",
    sw_version="sw",
    hw_version="hw",
)
TEST_DATA_OUT = TEST_USER_DATA | {
    "device_info": {k: v for k, v in TEST_DEVICE_INFO.items() if k != "id"}
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO.copy()
    ), patch(
        "homeassistant.components.airq.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DEVICE_INFO["name"]
    assert result2["data"] == TEST_DATA_OUT


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioairq.AirQ.fetch_device_info", side_effect=InvalidAuth):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_DATA | {CONF_PASSWORD: "wrong_password"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioairq.AirQ.fetch_device_info", side_effect=ClientConnectionError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_DATA
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_input(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioairq.AirQ.fetch_device_info", side_effect=InvalidInput):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_DATA | {CONF_IP_ADDRESS: "invalid_ip"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_input"}


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(
        data=TEST_USER_DATA,
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO["id"],
    ).add_to_hass(hass)

    with patch(
        "aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO.copy()
    ), patch(
        "homeassistant.components.airq.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_USER_DATA
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauthentication flow with possible errors handled correctly."""
    MockConfigEntry(
        data=TEST_USER_DATA,
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO["id"],
    ).add_to_hass(hass)

    with patch(
        "aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO.copy()
    ), patch(
        "homeassistant.components.airq.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": TEST_DEVICE_INFO["id"],
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch("aioairq.AirQ.fetch_device_info", side_effect=InvalidAuth):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_REAUTH_DATA | {CONF_PASSWORD: "wrong_password"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with patch("aioairq.AirQ.fetch_device_info", side_effect=ClientConnectionError):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_REAUTH_DATA
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}

    with patch(
        "aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO.copy()
    ), patch(
        "homeassistant.components.airq.async_setup_entry",
        return_value=True,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_REAUTH_DATA,
        )

    assert result4["type"] == "abort"
    assert result4["reason"] == "reauth_successful"
