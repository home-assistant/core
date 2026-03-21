"""Test the victron GX config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import AuthenticationError, CannotConnectError

from homeassistant.components.victron_gx.config_flow import DEFAULT_PORT
from homeassistant.components.victron_gx.const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

MOCK_INSTALLATION_ID = "d41243d9b9c6"
MOCK_SERIAL = "HQ2234ABCDE"
MOCK_MODEL = "Cerbo GX"
MOCK_FRIENDLY_NAME = "Venus GX"
MOCK_HOST = "192.168.1.100"


def assert_entry_title(
    result: dict[str, object],
    installation_id: str = MOCK_INSTALLATION_ID,
    host: str = MOCK_HOST,
    port: int = DEFAULT_PORT,
) -> None:
    """Assert the config entry title format."""
    assert result["title"] == f"Victron OS {installation_id} ({host}:{port})"


@pytest.fixture
def mock_victron_hub():
    """Mock the Victron Hub."""
    with patch(
        "homeassistant.components.victron_gx.config_flow.VictronVenusHub"
    ) as mock_hub:
        hub_instance = MagicMock()
        hub_instance.connect = AsyncMock()
        hub_instance.disconnect = AsyncMock()
        hub_instance.installation_id = MOCK_INSTALLATION_ID
        mock_hub.return_value = hub_instance
        yield mock_hub


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_full_config(hass: HomeAssistant) -> None:
    """Test the full user flow with all configuration options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID
    assert_entry_title(result)
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_SERIAL: None,
        CONF_MODEL: None,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
    }


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_minimal_config(hass: HomeAssistant) -> None:
    """Test the user flow with minimal configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID
    assert_entry_title(result)
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_SSL: False,
        CONF_SERIAL: None,
        CONF_MODEL: None,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (CannotConnectError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
        (AuthenticationError("Invalid credentials"), "invalid_auth"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    mock_victron_hub: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_victron_hub.return_value.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Recover from error
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID


@pytest.mark.usefixtures("mock_victron_hub", "mock_config_entry")
async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test configuration flow aborts when device is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_victron_hub")
async def test_ssdp_flow_success(hass: HomeAssistant) -> None:
    """Test SSDP discovery flow with successful connection."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID
    assert_entry_title(result)
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_MODEL: MOCK_MODEL,
    }


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (CannotConnectError("Cannot connect"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_ssdp_confirm_error(
    hass: HomeAssistant,
    mock_victron_hub: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test SSDP confirm step aborts on errors."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    mock_victron_hub.return_value.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_victron_hub", "mock_config_entry")
async def test_ssdp_flow_already_configured(hass: HomeAssistant) -> None:
    """Test SSDP discovery flow aborts when device is already configured."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_flow_auth_required(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP discovery flow when authentication is required."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_auth"

    # Test providing credentials
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID
    assert_entry_title(result)
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
    }


async def test_ssdp_auth_invalid_credentials(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP auth flow with invalid credentials."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_auth"

    # Test with wrong credentials
    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Invalid credentials"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "wrong-user",
            CONF_PASSWORD: "wrong-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Retry with correct credentials
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID
    assert_entry_title(result)
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (CannotConnectError("Cannot connect"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_ssdp_auth_error(
    hass: HomeAssistant,
    mock_victron_hub: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test SSDP auth flow error handling."""
    discovery_info = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="upnp:rootdevice",
        ssdp_location="http://192.168.1.100:80/",
        upnp={
            "serialNumber": MOCK_SERIAL,
            "X_VrmPortalId": MOCK_INSTALLATION_ID,
            "modelName": MOCK_MODEL,
            "friendlyName": MOCK_FRIENDLY_NAME,
            "X_MqttOnLan": "1",
            "manufacturer": "Victron Energy",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_confirm"

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_auth"

    mock_victron_hub.return_value.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_user_flow_disconnect_error_ignored(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test config flow succeeds even when disconnect raises."""
    mock_victron_hub.return_value.disconnect.side_effect = Exception("disconnect fail")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_INSTALLATION_ID


async def test_user_flow_missing_installation_id(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test config flow handles hub returning no installation id."""
    mock_victron_hub.return_value.installation_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
