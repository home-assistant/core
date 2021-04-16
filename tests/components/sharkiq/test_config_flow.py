"""Test the Shark IQ config flow."""
from unittest.mock import patch

import aiohttp
import pytest
from sharkiqpy import AylaApi, SharkIqAuthError

from homeassistant import config_entries, setup
from homeassistant.components.sharkiq.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import CONFIG, TEST_PASSWORD, TEST_USERNAME, UNIQUE_ID

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("sharkiqpy.AylaApi.async_sign_in", return_value=True), patch(
        "homeassistant.components.sharkiq.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == f"{TEST_USERNAME:s}"
    assert result2["data"] == {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    await hass.async_block_till_done()
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    "exc,base_error",
    [
        (SharkIqAuthError, "invalid_auth"),
        (aiohttp.ClientError, "cannot_connect"),
        (TypeError, "unknown"),
    ],
)
async def test_form_error(hass: HomeAssistant, exc: Exception, base_error: str):
    """Test form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(AylaApi, "async_sign_in", side_effect=exc):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"].get("base") == base_error


async def test_reauth_success(hass: HomeAssistant):
    """Test reauth flow."""
    with patch("sharkiqpy.AylaApi.async_sign_in", return_value=True):
        mock_config = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG)
        mock_config.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth", "unique_id": UNIQUE_ID}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    "side_effect,result_type,msg_field,msg",
    [
        (SharkIqAuthError, "form", "errors", "invalid_auth"),
        (aiohttp.ClientError, "abort", "reason", "cannot_connect"),
        (TypeError, "abort", "reason", "unknown"),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    side_effect: Exception,
    result_type: str,
    msg_field: str,
    msg: str,
):
    """Test reauth failures."""
    with patch("sharkiqpy.AylaApi.async_sign_in", side_effect=side_effect):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        msg_value = result[msg_field]
        if msg_field == "errors":
            msg_value = msg_value.get("base")

        assert result["type"] == result_type
        assert msg_value == msg
