"""Define tests for the Nettigo config flow."""
import asyncio
from unittest.mock import patch

from nettigo import ApiError, CannotGetMac
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.nettigo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_HOST: "10.10.2.3"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_form_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.nettigo.Nettigo.async_get_mac_address",
        return_value="aa:bb:cc:dd:ee:ff",
    ), patch("homeassistant.components.nettigo.async_setup_entry", return_value=True):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "10.10.2.3"
        assert result["data"][CONF_HOST] == "10.10.2.3"


@pytest.mark.parametrize(
    "error",
    [
        (ApiError("Invalid response from device 10.10.2.3: 404"), "cannot_connect"),
        (asyncio.TimeoutError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(hass, error):
    """Test we handle errors."""
    exc, base_error = error
    with patch(
        "homeassistant.components.nettigo.Nettigo.async_get_mac_address",
        side_effect=exc,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": base_error}


async def test_form_abort(hass):
    """Test we handle errors."""
    with patch(
        "homeassistant.components.nettigo.Nettigo.async_get_mac_address",
        side_effect=CannotGetMac("Cannot get MAC address from device"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "device_unsupported"


async def test_form_already_configured(hass):
    """Test we get the form."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="aa:bb:cc:dd:ee:ff", data=VALID_CONFIG
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nettigo.Nettigo.async_get_mac_address",
        return_value="aa:bb:cc:dd:ee:ff",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"
