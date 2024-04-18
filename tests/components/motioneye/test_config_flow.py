"""Test the motionEye config flow."""

from unittest.mock import AsyncMock, patch

from motioneye_client.client import (
    MotionEyeClientConnectionError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientRequestError,
)

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.motioneye.const import (
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    CONF_WEBHOOK_SET,
    CONF_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
)
from homeassistant.const import CONF_URL, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_URL, create_mock_motioneye_client, create_mock_motioneye_config_entry

from tests.common import MockConfigEntry


async def test_user_success(hass: HomeAssistant) -> None:
    """Test successful user flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    mock_client = create_mock_motioneye_client()

    with (
        patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.motioneye.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
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


async def test_hassio_success(hass: HomeAssistant) -> None:
    """Test successful Supervisor flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "motionEye", "url": TEST_URL},
            name="motionEye",
            slug="motioneye",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "hassio_confirm"
    assert result.get("description_placeholders") == {"addon": "motionEye"}

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "user"

    mock_client = create_mock_motioneye_client()

    with (
        patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.motioneye.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Add-on"
    assert result3.get("data") == {
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_client.async_client_close.called


async def test_user_invalid_url(hass: HomeAssistant) -> None:
    """Test invalid url is handled correctly."""

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

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
    assert mock_client.async_client_close.called


async def test_reauth(hass: HomeAssistant) -> None:
    """Test a reauth."""
    config_data = {
        CONF_URL: TEST_URL,
        CONF_WEBHOOK_ID: "test-webhook-id",
    }

    config_entry = create_mock_motioneye_config_entry(hass, data=config_data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    mock_client = create_mock_motioneye_client()

    new_data = {
        CONF_URL: TEST_URL,
        CONF_ADMIN_USERNAME: "admin-username",
        CONF_ADMIN_PASSWORD: "admin-password",
        CONF_SURVEILLANCE_USERNAME: "surveillance-username",
        CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
    }

    with (
        patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.motioneye.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            new_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert dict(config_entry.data) == {**new_data, CONF_WEBHOOK_ID: "test-webhook-id"}

    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_client.async_client_close.called


async def test_duplicate(hass: HomeAssistant) -> None:
    """Test that a duplicate entry (same URL) is rejected."""
    config_data = {
        CONF_URL: TEST_URL,
    }

    # Add an existing entry with the same URL.
    existing_entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
    )
    existing_entry.add_to_hass(hass)

    # Now do the usual config entry process, and verify it is rejected.
    create_mock_motioneye_config_entry(hass, data=config_data)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_client.async_client_close.called


async def test_hassio_already_configured(hass: HomeAssistant) -> None:
    """Test we don't discover when already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: TEST_URL},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "motionEye", "url": TEST_URL},
            name="motionEye",
            slug="motioneye",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_hassio_ignored(hass: HomeAssistant) -> None:
    """Test Supervisor discovered instance can be ignored."""
    MockConfigEntry(domain=DOMAIN, source=config_entries.SOURCE_IGNORE).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "motionEye", "url": TEST_URL},
            name="motionEye",
            slug="motioneye",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_hassio_abort_if_already_in_progress(hass: HomeAssistant) -> None:
    """Test Supervisor discovered flow aborts if user flow in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "motionEye", "url": TEST_URL},
            name="motionEye",
            slug="motioneye",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_in_progress"


async def test_hassio_clean_up_on_user_flow(hass: HomeAssistant) -> None:
    """Test Supervisor discovered flow is clean up when doing user flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=HassioServiceInfo(
            config={"addon": "motionEye", "url": TEST_URL},
            name="motionEye",
            slug="motioneye",
            uuid="1234",
        ),
        context={"source": config_entries.SOURCE_HASSIO},
    )
    assert result.get("type") is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result2.get("type") is FlowResultType.FORM

    mock_client = create_mock_motioneye_client()

    with (
        patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.motioneye.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_ADMIN_USERNAME: "admin-username",
                CONF_ADMIN_PASSWORD: "admin-password",
                CONF_SURVEILLANCE_USERNAME: "surveillance-username",
                CONF_SURVEILLANCE_PASSWORD: "surveillance-password",
            },
        )
        await hass.async_block_till_done()

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


async def test_options(hass: HomeAssistant) -> None:
    """Check an options flow."""

    config_entry = create_mock_motioneye_config_entry(hass)

    client = create_mock_motioneye_client()
    with (
        patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.motioneye.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_WEBHOOK_SET: True,
                CONF_WEBHOOK_SET_OVERWRITE: True,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_SET]
        assert result["data"][CONF_WEBHOOK_SET_OVERWRITE]
        assert CONF_STREAM_URL_TEMPLATE not in result["data"]


async def test_advanced_options(hass: HomeAssistant) -> None:
    """Check an options flow with advanced options."""

    config_entry = create_mock_motioneye_config_entry(hass)

    mock_client = create_mock_motioneye_client()
    with (
        patch(
            "homeassistant.components.motioneye.MotionEyeClient",
            return_value=mock_client,
        ) as mock_setup,
        patch(
            "homeassistant.components.motioneye.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, context={"show_advanced_options": True}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_WEBHOOK_SET: True,
                CONF_WEBHOOK_SET_OVERWRITE: True,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_SET]
        assert result["data"][CONF_WEBHOOK_SET_OVERWRITE]
        assert CONF_STREAM_URL_TEMPLATE not in result["data"]
        assert len(mock_setup.mock_calls) == 0
        assert len(mock_setup_entry.mock_calls) == 0

        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, context={"show_advanced_options": True}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_WEBHOOK_SET: True,
                CONF_WEBHOOK_SET_OVERWRITE: True,
                CONF_STREAM_URL_TEMPLATE: "http://moo",
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_SET]
        assert result["data"][CONF_WEBHOOK_SET_OVERWRITE]
        assert result["data"][CONF_STREAM_URL_TEMPLATE] == "http://moo"
        assert len(mock_setup.mock_calls) == 0
        assert len(mock_setup_entry.mock_calls) == 0
