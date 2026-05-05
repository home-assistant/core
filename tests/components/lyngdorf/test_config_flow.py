"""Configuration flow tests for the Lyngdorf integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from lyngdorf.const import LyngdorfModel
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
async def test_user_flow_cannot_determine_id_recovers(
    hass: HomeAssistant,
    mock_get_device_serial: AsyncMock,
) -> None:
    """Test user flow shows error when serial cannot be determined, then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_get_device_serial.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_determine_id"}

    mock_get_device_serial.return_value = MOCK_SERIAL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_SERIAL


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_device_serial")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

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
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"


@pytest.mark.usefixtures("mock_get_device_serial")
async def test_user_flow_unsupported_model_recovers(
    hass: HomeAssistant,
    mock_find_receiver_model: AsyncMock,
) -> None:
    """Test user flow shows unsupported_model error, then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_find_receiver_model.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_model"}

    mock_find_receiver_model.return_value = LyngdorfModel.MP_60
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (ConnectionError("Unable to connect"), "cannot_connect"),
        (TimeoutError("Connection timeout"), "timeout_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
    ids=["cannot_connect", "timeout", "unknown"],
)
@pytest.mark.usefixtures("mock_get_device_serial")
async def test_user_flow_connection_errors_recover(
    hass: HomeAssistant,
    mock_find_receiver_model: AsyncMock,
    exc: Exception,
    expected_error: str,
) -> None:
    """Test user flow surfaces connection errors and then recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_find_receiver_model.side_effect = exc
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_find_receiver_model.side_effect = None
    mock_find_receiver_model.return_value = LyngdorfModel.MP_60
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
                ATTR_UPNP_SERIAL: MOCK_SERIAL,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert config_entry.unique_id == MOCK_SERIAL
    assert config_entry.title == "Living Room"
    assert config_entry.data[CONF_HOST] == "192.168.1.100"
    assert config_entry.data[CONF_SERIAL_NUMBER] == MOCK_SERIAL


async def test_ssdp_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test SSDP discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

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
                ATTR_UPNP_SERIAL: MOCK_SERIAL,
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.100"


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


async def test_ssdp_discovery_connection_failure(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when the device cannot be reached."""
    with patch(
        "homeassistant.components.lyngdorf.config_flow.async_find_receiver_model",
        side_effect=OSError("Connection refused"),
    ):
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
                    ATTR_UPNP_SERIAL: MOCK_SERIAL,
                },
            ),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
