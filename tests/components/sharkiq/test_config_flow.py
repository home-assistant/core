"""Test the Shark IQ config flow."""

from unittest.mock import patch

import aiohttp
import pytest
from sharkiq import AylaApi, SharkIqAuthError, SharkIqError

from homeassistant import config_entries
from homeassistant.components.sharkiq.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .const import (
    CONFIG,
    CONFIG_NO_REGION,
    TEST_PASSWORD,
    TEST_REGION,
    TEST_USERNAME,
    UNIQUE_ID,
)

from tests.common import MockConfigEntry


async def test_setup_success_no_region(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG_NO_REGION
    )
    mock_config.add_to_hass(hass)

    result = await async_setup_component(hass=hass, domain=DOMAIN, config={})

    assert result is True


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch("sharkiq.AylaApi.async_sign_in", return_value=True),
        patch(
            "homeassistant.components.sharkiq.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"{TEST_USERNAME:s}"
    assert result2["data"] == {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "region": TEST_REGION,
    }

    await hass.async_block_till_done()
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (SharkIqAuthError, "invalid_auth"),
        (aiohttp.ClientError, "cannot_connect"),
        (TypeError, "cannot_connect"),
        (SharkIqError, "unknown"),
    ],
)
async def test_form_error(hass: HomeAssistant, exc: Exception, base_error: str) -> None:
    """Test form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(AylaApi, "async_sign_in", side_effect=exc):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"].get("base") == base_error


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    with patch("sharkiq.AylaApi.async_sign_in", return_value=True):
        mock_config = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG)
        mock_config.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("side_effect", "result_type", "msg_field", "msg"),
    [
        (SharkIqAuthError, "form", "errors", "invalid_auth"),
        (aiohttp.ClientError, "abort", "reason", "cannot_connect"),
        (TypeError, "abort", "reason", "cannot_connect"),
        (SharkIqError, "abort", "reason", "unknown"),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    side_effect: Exception,
    result_type: str,
    msg_field: str,
    msg: str,
) -> None:
    """Test reauth failures."""
    with patch("sharkiq.AylaApi.async_sign_in", side_effect=side_effect):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        msg_value = result[msg_field]
        if msg_field == "errors":
            msg_value = msg_value.get("base")

        assert result["type"] == result_type
        assert msg_value == msg
