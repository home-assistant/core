"""Configuration flow tests for the Lyngdorf integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lyngdorf import LyngdorfModel
import pytest

from homeassistant.components.lyngdorf.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_SERIAL = "0050c27c76b2"


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_user_flow(
    hass: HomeAssistant, mock_get_device_serial: AsyncMock
) -> None:
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
    assert mock_get_device_serial.call_args.kwargs[
        "session"
    ] is async_get_clientsession(hass)


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


@pytest.mark.parametrize(
    ("friendly_name", "expected_title"),
    [
        pytest.param("Living Room", "Living Room", id="custom_name"),
        pytest.param("mp-60", "mp-60", id="name_matches_model"),
    ],
)
@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_ssdp_discovery(
    hass: HomeAssistant, friendly_name: str, expected_title: str
) -> None:
    """Test successful SSDP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.100/desc.xml",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: friendly_name,
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
    assert config_entry.title == expected_title
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
    assert result["reason"] == "cannot_determine_id"


async def test_ssdp_discovery_unsupported_model(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert "UNKNOWN-MODEL" in caplog.text


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


@pytest.mark.parametrize(
    "ssdp_location",
    [
        pytest.param(None, id="no_location"),
        pytest.param("http:///desc.xml", id="no_hostname"),
    ],
)
async def test_ssdp_discovery_no_host(
    hass: HomeAssistant, ssdp_location: str | None
) -> None:
    """Test SSDP discovery aborts when no hostname can be determined."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=ssdp_location,
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "Living Room",
                ATTR_UPNP_MODEL_NAME: "MP-60",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(OSError("Connection refused"), "cannot_connect", id="os_error"),
        pytest.param(
            TimeoutError("Connection timeout"), "cannot_connect", id="timeout"
        ),
        pytest.param(None, "unsupported_model", id="model_not_found"),
    ],
)
async def test_ssdp_discovery_connectivity_check_aborts(
    hass: HomeAssistant,
    mock_find_receiver_model: AsyncMock,
    side_effect: Exception | None,
    expected_reason: str,
) -> None:
    """Test SSDP discovery aborts when the connectivity check fails."""
    mock_find_receiver_model.side_effect = side_effect
    mock_find_receiver_model.return_value = None

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
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("mock_find_receiver_model", "mock_get_device_serial")
async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an entry updates the host."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.50"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.50"


@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_reconfigure_different_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_device_serial: AsyncMock,
) -> None:
    """Test an entry cannot be pointed at a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_get_device_serial.return_value = "aabbccddeeff"
    original_host = mock_config_entry.data[CONF_HOST]

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.50"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_HOST] == original_host


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TimeoutError, "timeout_connect"),
        (OSError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_get_device_serial")
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_find_receiver_model: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test reconfigure surfaces connection errors and recovers."""
    mock_config_entry.add_to_hass(hass)
    mock_find_receiver_model.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.50"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_find_receiver_model.side_effect = None
    mock_find_receiver_model.return_value = LyngdorfModel.MP_60
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.50"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TimeoutError, "timeout_connect"),
        (OSError, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_find_receiver_model")
async def test_user_flow_serial_errors(
    hass: HomeAssistant,
    mock_get_device_serial: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test a failure to read the serial is surfaced on the form."""
    mock_get_device_serial.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_get_device_serial.side_effect = None
    mock_get_device_serial.return_value = "0050c27c76b2"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("model", "serial", "error"),
    [
        pytest.param(None, "0050c27c76b2", "unsupported_model", id="unsupported"),
        pytest.param(LyngdorfModel.MP_60, None, "cannot_determine_id", id="no_serial"),
    ],
)
async def test_reconfigure_device_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_find_receiver_model: AsyncMock,
    mock_get_device_serial: AsyncMock,
    model: LyngdorfModel | None,
    serial: str | None,
    error: str,
) -> None:
    """Test reconfigure surfaces a device it cannot identify."""
    mock_config_entry.add_to_hass(hass)
    mock_find_receiver_model.return_value = model
    mock_get_device_serial.return_value = serial

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_find_receiver_model.return_value = LyngdorfModel.MP_60
    mock_get_device_serial.return_value = "0050c27c76b2"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
