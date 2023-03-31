"""Tests for the MJPEG IP Camera config flow."""

from unittest.mock import AsyncMock

import requests
from requests_mock import Mocker

from homeassistant.components.mjpeg.const import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_mjpeg_requests: Mocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Spy cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_STILL_IMAGE_URL: "https://example.com/still",
            CONF_USERNAME: "frenck",
            CONF_PASSWORD: "omgpuppies",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Spy cam"
    assert result2.get("data") == {}
    assert result2.get("options") == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_MJPEG_URL: "https://example.com/mjpeg",
        CONF_PASSWORD: "omgpuppies",
        CONF_STILL_IMAGE_URL: "https://example.com/still",
        CONF_USERNAME: "frenck",
        CONF_VERIFY_SSL: False,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_mjpeg_requests.call_count == 2


async def test_full_flow_with_authentication_error(
    hass: HomeAssistant,
    mock_mjpeg_requests: Mocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow with invalid credentials.

    This tests tests a full config flow, with a case the user enters an invalid
    credentials, but recovers by entering the correct ones.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    mock_mjpeg_requests.get(
        "https://example.com/mjpeg", text="Access Denied!", status_code=401
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Sky cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_PASSWORD: "omgpuppies",
            CONF_USERNAME: "frenck",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {"username": "invalid_auth"}

    assert len(mock_setup_entry.mock_calls) == 0
    assert mock_mjpeg_requests.call_count == 2

    mock_mjpeg_requests.get("https://example.com/mjpeg", text="resp")
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_NAME: "Sky cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_PASSWORD: "supersecret",
            CONF_USERNAME: "frenck",
        },
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Sky cam"
    assert result3.get("data") == {}
    assert result3.get("options") == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_MJPEG_URL: "https://example.com/mjpeg",
        CONF_PASSWORD: "supersecret",
        CONF_STILL_IMAGE_URL: None,
        CONF_USERNAME: "frenck",
        CONF_VERIFY_SSL: True,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_mjpeg_requests.call_count == 3


async def test_connection_error(
    hass: HomeAssistant,
    mock_mjpeg_requests: Mocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    # Test connectione error on MJPEG url
    mock_mjpeg_requests.get(
        "https://example.com/mjpeg", exc=requests.exceptions.ConnectionError
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "My cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_STILL_IMAGE_URL: "https://example.com/still",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {"mjpeg_url": "cannot_connect"}

    assert len(mock_setup_entry.mock_calls) == 0
    assert mock_mjpeg_requests.call_count == 1

    # Reset
    mock_mjpeg_requests.get("https://example.com/mjpeg", text="resp")

    # Test connectione error on still url
    mock_mjpeg_requests.get(
        "https://example.com/still", exc=requests.exceptions.ConnectionError
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_NAME: "My cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_STILL_IMAGE_URL: "https://example.com/still",
        },
    )

    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == SOURCE_USER
    assert result3.get("errors") == {"still_image_url": "cannot_connect"}

    assert len(mock_setup_entry.mock_calls) == 0
    assert mock_mjpeg_requests.call_count == 3

    # Reset
    mock_mjpeg_requests.get("https://example.com/still", text="resp")

    # Finish
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            CONF_NAME: "My cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_STILL_IMAGE_URL: "https://example.com/still",
        },
    )

    assert result4.get("type") == FlowResultType.CREATE_ENTRY
    assert result4.get("title") == "My cam"
    assert result4.get("data") == {}
    assert result4.get("options") == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_MJPEG_URL: "https://example.com/mjpeg",
        CONF_PASSWORD: "",
        CONF_STILL_IMAGE_URL: "https://example.com/still",
        CONF_USERNAME: None,
        CONF_VERIFY_SSL: True,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert mock_mjpeg_requests.call_count == 5


async def test_already_configured(
    hass: HomeAssistant,
    mock_mjpeg_requests: Mocker,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we abort if the MJPEG IP Camera is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "My cam",
            CONF_MJPEG_URL: "https://example.com/mjpeg",
        },
    )

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_mjpeg_requests: Mocker,
    init_integration: MockConfigEntry,
) -> None:
    """Test options config flow."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"

    # Register a second camera
    mock_mjpeg_requests.get("https://example.com/second_camera", text="resp")
    mock_second_config_entry = MockConfigEntry(
        title="Another Camera",
        domain=DOMAIN,
        data={},
        options={
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_MJPEG_URL: "https://example.com/second_camera",
            CONF_PASSWORD: "",
            CONF_STILL_IMAGE_URL: None,
            CONF_USERNAME: None,
            CONF_VERIFY_SSL: True,
        },
    )
    mock_second_config_entry.add_to_hass(hass)

    # Try updating options to already existing secondary camera
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MJPEG_URL: "https://example.com/second_camera",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "init"
    assert result2.get("errors") == {"mjpeg_url": "already_configured"}

    assert mock_mjpeg_requests.call_count == 1

    # Test connectione error on MJPEG url
    mock_mjpeg_requests.get(
        "https://example.com/invalid_mjpeg", exc=requests.exceptions.ConnectionError
    )
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={
            CONF_MJPEG_URL: "https://example.com/invalid_mjpeg",
            CONF_STILL_IMAGE_URL: "https://example.com/still",
        },
    )

    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == "init"
    assert result3.get("errors") == {"mjpeg_url": "cannot_connect"}

    assert mock_mjpeg_requests.call_count == 2

    # Test connectione error on still url
    mock_mjpeg_requests.get(
        "https://example.com/invalid_still", exc=requests.exceptions.ConnectionError
    )
    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_STILL_IMAGE_URL: "https://example.com/invalid_still",
        },
    )

    assert result4.get("type") == FlowResultType.FORM
    assert result4.get("step_id") == "init"
    assert result4.get("errors") == {"still_image_url": "cannot_connect"}

    assert mock_mjpeg_requests.call_count == 4

    # Invalid credentials
    mock_mjpeg_requests.get(
        "https://example.com/invalid_auth", text="Access Denied!", status_code=401
    )
    result5 = await hass.config_entries.options.async_configure(
        result4["flow_id"],
        user_input={
            CONF_MJPEG_URL: "https://example.com/invalid_auth",
            CONF_PASSWORD: "omgpuppies",
            CONF_USERNAME: "frenck",
        },
    )

    assert result5.get("type") == FlowResultType.FORM
    assert result5.get("step_id") == "init"
    assert result5.get("errors") == {"username": "invalid_auth"}

    assert mock_mjpeg_requests.call_count == 6

    # Finish
    result6 = await hass.config_entries.options.async_configure(
        result5["flow_id"],
        user_input={
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_PASSWORD: "evenmorepuppies",
            CONF_USERNAME: "newuser",
        },
    )

    assert result6.get("type") == FlowResultType.CREATE_ENTRY
    assert result6.get("data") == {
        CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        CONF_MJPEG_URL: "https://example.com/mjpeg",
        CONF_PASSWORD: "evenmorepuppies",
        CONF_STILL_IMAGE_URL: None,
        CONF_USERNAME: "newuser",
        CONF_VERIFY_SSL: True,
    }

    assert mock_mjpeg_requests.call_count == 7
