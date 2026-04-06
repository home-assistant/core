"""Configuration flow tests for the Lyngdorf integration."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lyngdorf.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_SERIAL = "0050c27c76b2"


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_device_serial")
async def test_user_flow_shows_form(hass: HomeAssistant) -> None:
    """Test user flow shows the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_device_serial")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the user configuration flow with serial lookup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == MOCK_SERIAL
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert config_entry.data[CONF_SERIAL_NUMBER] == MOCK_SERIAL
    assert config_entry.title == "mp-60"


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_user_flow_cannot_determine_id(hass: HomeAssistant) -> None:
    """Test user flow shows error when serial cannot be determined."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_get_device_serial",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_determine_id"}


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_device_serial")
async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow when device is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={CONF_HOST: "192.168.1.50"},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Host should NOT be updated (no updates= in _abort_if_unique_id_configured)
    assert existing_entry.data[CONF_HOST] == "192.168.1.50"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (None, "unsupported_model"),
        (ConnectionError("Unable to connect"), "cannot_connect"),
        (TimeoutError("Connection timeout"), "timeout_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
    ids=["unsupported_model", "cannot_connect", "timeout", "unknown"],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    side_effect: Exception | None,
    expected_error: str,
) -> None:
    """Test user flow error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_kwargs: dict[str, Any] = {}
    if side_effect is not None:
        mock_kwargs["side_effect"] = side_effect
    else:
        mock_kwargs["return_value"] = None

    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        new=AsyncMock(**mock_kwargs),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_ssdp_discovery(hass: HomeAssistant) -> None:
    """Test successful SSDP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "MP-60",
                ATTR_UPNP_SERIAL: "123456",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == "123456"
    assert config_entry.title == "Living Room"
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert config_entry.data[CONF_SERIAL_NUMBER] == "123456"


async def test_ssdp_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when device is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data={CONF_HOST: "192.168.1.50"},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "MP-60",
                ATTR_UPNP_SERIAL: "123456",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing_entry.data[CONF_HOST] == "192.168.1.100"


async def test_ssdp_discovery_no_serial(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no serial number is available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "MP-60",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_discovery_unsupported_model(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when model is not supported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "UNKNOWN-MODEL",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"


async def test_ssdp_discovery_missing_model(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when model name is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_model"


async def test_ssdp_discovery_no_location(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when no hostname can be determined."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=None,
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "MP-60",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_confirm_connection_failure(hass: HomeAssistant) -> None:
    """Test SSDP confirm step shows error when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "MP-60",
                ATTR_UPNP_SERIAL: "123456",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        new=AsyncMock(side_effect=OSError("Connection refused")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "cannot_connect"}
