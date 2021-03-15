"""Test the motionEye config flow."""
import logging
from unittest.mock import AsyncMock, patch

from motioneye_client.client import (
    MotionEyeClientConnectionFailure,
    MotionEyeClientInvalidAuth,
)

from homeassistant import config_entries, setup
from homeassistant.components.motioneye.const import CONF_BASE_URL, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from . import create_mock_motioneye_client

_LOGGER = logging.getLogger(__name__)


async def test_user_success(hass):
    """Test successful user flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    mock_client = create_mock_motioneye_client()

    with patch(
        "homeassistant.components.motioneye.config_flow.MotionEyeClient",
        return_value=mock_client,
    ), patch(
        "homeassistant.components.motioneye.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.motioneye.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "http://localhost"
    assert result["data"] == {
        CONF_BASE_URL: "http://localhost",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_invalid_auth(hass):
    """Test invalid auth is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(side_effect=MotionEyeClientInvalidAuth)

    with patch(
        "homeassistant.components.motioneye.config_flow.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await mock_client.async_client_close()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_cannot_connect(hass):
    """Test connection failure is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(
        side_effect=MotionEyeClientConnectionFailure
    )

    with patch(
        "homeassistant.components.motioneye.config_flow.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_BASE_URL: "http://localhost",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await mock_client.async_client_close()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
