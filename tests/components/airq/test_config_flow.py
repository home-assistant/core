"""Test the air-Q config flow."""

from unittest.mock import patch

from aioairq import DeviceInfo, InvalidAuth
from aiohttp.client_exceptions import ClientConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.airq.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

TEST_USER_DATA = {
    CONF_IP_ADDRESS: "192.168.0.0",
    CONF_PASSWORD: "password",
}
TEST_DEVICE_INFO = DeviceInfo(
    id="id",
    name="name",
    model="model",
    sw_version="sw",
    hw_version="hw",
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch("aioairq.AirQ.validate"),
        patch("aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DEVICE_INFO["name"]
    assert result2["data"] == TEST_USER_DATA


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioairq.AirQ.validate", side_effect=InvalidAuth):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_DATA | {CONF_PASSWORD: "wrong_password"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("aioairq.AirQ.validate", side_effect=ClientConnectionError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_DATA
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(
        data=TEST_USER_DATA,
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO["id"],
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("aioairq.AirQ.validate"),
        patch("aioairq.AirQ.fetch_device_info", return_value=TEST_DEVICE_INFO),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_DATA
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
