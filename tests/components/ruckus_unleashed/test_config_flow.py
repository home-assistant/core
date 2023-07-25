"""Test the Ruckus Unleashed config flow."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioruckus.const import CONNECT_ERROR_TIMEOUT, LOGIN_ERROR_LOGIN_INCORRECT
from aioruckus.exceptions import AuthenticationError

from homeassistant import config_entries
from homeassistant.components.ruckus_unleashed.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import utcnow

from . import CONFIG, DEFAULT_TITLE, RuckusAjaxApiPatchContext

from tests.common import async_fire_time_changed


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with RuckusAjaxApiPatchContext(), patch(
        "homeassistant.components.ruckus_unleashed.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

        assert result2["type"] == "create_entry"
        assert result2["title"] == DEFAULT_TITLE
        assert result2["data"] == CONFIG
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(
            side_effect=AuthenticationError(LOGIN_ERROR_LOGIN_INCORRECT)
        )
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(
        login_mock=AsyncMock(side_effect=ConnectionError(CONNECT_ERROR_TIMEOUT))
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext(login_mock=AsyncMock(side_effect=Exception)):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_cannot_connect_unknown_serial(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error on invalid serial number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with RuckusAjaxApiPatchContext(system_info={}):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_duplicate_error(hass: HomeAssistant) -> None:
    """Test we handle duplicate error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with RuckusAjaxApiPatchContext():
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        future = utcnow() + timedelta(minutes=60)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"
