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
from homeassistant.core import HomeAssistant

from . import TEST_URL, create_mock_motioneye_client, create_mock_motioneye_config_entry

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_user_success(hass: HomeAssistant) -> None:
    """Test successful user flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    mock_client = create_mock_motioneye_client()

    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=mock_client,
    ), patch(
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
    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_client.async_client_close.called


async def test_user_invalid_auth(hass: HomeAssistant) -> None:
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
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_client.async_client_close.called


async def test_user_invalid_url(hass: HomeAssistant) -> None:
    """Test invalid url is handled correctly."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client = create_mock_motioneye_client()
    with patch(
        "homeassistant.components.motioneye.MotionEyeClient",
        return_value=mock_client,
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
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_cannot_connect(hass: HomeAssistant) -> None:
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
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_client.async_client_close.called


async def test_user_request_error(hass: HomeAssistant) -> None:
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
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
    assert mock_client.async_client_close.called


async def test_reauth(hass: HomeAssistant) -> None:
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
    assert not result["errors"]

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

    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_client.async_client_close.called


async def test_duplicate(hass: HomeAssistant) -> None:
    """Test that a duplicate entry (same URL) is rejected."""
    config_data = {
        CONF_URL: TEST_URL,
    }

    # Add an existing entry with the same URL.
    existing_entry: MockConfigEntry = MockConfigEntry(  # type: ignore[no-untyped-call]
        domain=DOMAIN,
        data=config_data,
    )
    existing_entry.add_to_hass(hass)  # type: ignore[no-untyped-call]

    # Now do the usual config entry process, and verify it is rejected.
    create_mock_motioneye_config_entry(hass, data=config_data)

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert not result["errors"]
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
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_data,
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert mock_client.async_client_close.called
