"""Test the Shark IQ config flow."""
import aiohttp
from sharkiqpy import SharkIqAuthError

from homeassistant import config_entries, setup
from homeassistant.components.sharkiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import TEST_PASSWORD, TEST_USERNAME

from tests.async_mock import MagicMock, PropertyMock, patch


def _create_mocked_ayla(connect=None):
    """Create a mocked AylaApi object."""
    mocked_ayla = MagicMock()
    type(mocked_ayla).sign_in = PropertyMock(side_effect=connect)
    type(mocked_ayla).async_sign_in = PropertyMock(side_effect=connect)
    return mocked_ayla


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("sharkiqpy.AylaApi.async_sign_in", return_value=True,), patch(
        "homeassistant.components.sharkiq.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.sharkiq.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == f"Shark IQ ({TEST_USERNAME:s})"
    assert result2["data"] == {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_ayla = _create_mocked_ayla(connect=SharkIqAuthError)

    with patch(
        "homeassistant.components.sharkiq.config_flow.get_ayla_api",
        return_value=mocked_ayla,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mocked_ayla = _create_mocked_ayla(connect=aiohttp.ClientError)

    with patch(
        "homeassistant.components.sharkiq.config_flow.get_ayla_api",
        return_value=mocked_ayla,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
