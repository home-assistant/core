"""Test the motionEye config flow."""
import logging
from unittest.mock import AsyncMock, patch

from motioneye_client.client import (
    MotionEyeClientConnectionError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientRequestError,
)

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.motioneye.const import (
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_CONFIG_ENTRY,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    DOMAIN,
)
from homeassistant.const import CONF_URL
from homeassistant.helpers.typing import HomeAssistantType

from . import TEST_URL, create_mock_motioneye_client, create_mock_motioneye_config_entry

_LOGGER = logging.getLogger(__name__)


async def test_user_success(hass: HomeAssistantType) -> None:
    """Test successful user flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_client = create_mock_motioneye_client()

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
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
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == f"{TEST_URL}"
    assert result["data"] == {
        CONF_URL: TEST_URL,
        CONF_ADMIN_USERNAME: "admin-username",
        CONF_ADMIN_PASSWORD: "admin-password",
        CONF_SURVEILLANCE_USERNAME: "surveillance-username",
        CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_invalid_auth(hass: HomeAssistantType) -> None:
    """Test invalid auth is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(
        side_effect=MotionEyeClientInvalidAuthError
    )

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await mock_client.async_client_close()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_invalid_url(hass: HomeAssistantType) -> None:
    """Test invalid url is handled correctly."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=create_mock_motioneye_client(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "not a url",
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_cannot_connect(hass: HomeAssistantType) -> None:
    """Test connection failure is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(
        side_effect=MotionEyeClientConnectionError,
    )

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await mock_client.async_client_close()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_request_error(hass: HomeAssistantType) -> None:
    """Test a request error is handled correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    mock_client.async_client_login = AsyncMock(side_effect=MotionEyeClientRequestError)

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await mock_client.async_client_close()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_reauth(hass: HomeAssistantType) -> None:
    """Test a reauth."""
    config_data = {
        CONF_URL: TEST_URL,
    }

    config_entry = create_mock_motioneye_config_entry(hass, data=config_data)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            CONF_CONFIG_ENTRY: config_entry,
        },
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_client = create_mock_motioneye_client()

    new_data = {
        CONF_URL: TEST_URL,
        CONF_ADMIN_USERNAME: "admin-username",
        CONF_ADMIN_PASSWORD: "admin-password",
        CONF_SURVEILLANCE_USERNAME: "surveillance-username",
        CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
    }

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ), patch(
        "homeassistant.components.motioneye.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.motioneye.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_data,
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"
        assert config_entry.data == new_data

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
