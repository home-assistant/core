"""Test the victron GX config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import CannotConnectError
from victron_mqtt.hub import AuthenticationError

from homeassistant.components.victron_gx_mqtt.const import (
    CONF_INSTALLATION_ID,
    CONF_MODEL,
    CONF_ROOT_TOPIC_PREFIX,
    CONF_SERIAL,
    CONF_UPDATE_FREQUENCY_SECONDS,
    DEFAULT_PORT,
    DEFAULT_UPDATE_FREQUENCY_SECONDS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_SSDP, SOURCE_USER
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


@pytest.fixture
def mock_victron_hub():
    """Mock the Victron Hub."""
    with patch(
        "homeassistant.components.victron_gx_mqtt.config_flow.VictronVenusHub"
    ) as mock_hub:
        hub_instance = MagicMock()
        hub_instance.connect = AsyncMock()
        hub_instance.installation_id = MOCK_INSTALLATION_ID
        mock_hub.return_value = hub_instance
        yield mock_hub


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
            CONF_ROOT_TOPIC_PREFIX: "N/test",
            CONF_UPDATE_FREQUENCY_SECONDS: 60,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Victron OS {MOCK_INSTALLATION_ID}"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SSL: False,
        CONF_ROOT_TOPIC_PREFIX: "N/test",
        CONF_UPDATE_FREQUENCY_SECONDS: 60,
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
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Victron OS {MOCK_INSTALLATION_ID}"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_SSL: False,
        CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
    }


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_victron_hub.return_value.connect.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test we handle authentication errors in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Invalid credentials"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Recover from error with valid credentials
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_victron_hub")
async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test configuration flow aborts when device is already configured."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
    )
    mock_config_entry.add_to_hass(hass)

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
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_FRIENDLY_NAME
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_MODEL: MOCK_MODEL,
    }


async def test_ssdp_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP discovery flow when connection fails, falls back to user flow."""
    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

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

    # Should fall back to user form when connection fails
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("mock_victron_hub")
async def test_ssdp_flow_already_configured(hass: HomeAssistant) -> None:
    """Test SSDP discovery flow aborts when device is already configured."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
    )
    mock_config_entry.add_to_hass(hass)

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
    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

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
    assert result["title"] == f"{MOCK_MODEL} ({MOCK_SERIAL})"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


async def test_ssdp_auth_invalid_credentials(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP auth flow with invalid credentials."""
    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

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
    assert result["title"] == f"{MOCK_MODEL} ({MOCK_SERIAL})"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_SERIAL: MOCK_SERIAL,
        CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    }


async def test_ssdp_auth_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP auth flow when connection fails."""
    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

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
    assert result["step_id"] == "ssdp_auth"

    # Test connection error
    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_victron_hub")
async def test_options_flow_success(hass: HomeAssistant) -> None:
    """Test options flow allows updating configuration."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SERIAL: MOCK_SERIAL,
            CONF_MODEL: MOCK_MODEL,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.168.1.200",
                CONF_PORT: 1883,
                CONF_USERNAME: "new-user",
                CONF_PASSWORD: "new-pass",
                CONF_SSL: True,
                CONF_ROOT_TOPIC_PREFIX: "N/updated",
                CONF_UPDATE_FREQUENCY_SECONDS: 45,
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert mock_config_entry.data == {
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 1883,
            CONF_USERNAME: "new-user",
            CONF_PASSWORD: "new-pass",
            CONF_SSL: True,
            CONF_ROOT_TOPIC_PREFIX: "N/updated",
            CONF_UPDATE_FREQUENCY_SECONDS: 45,
        }
        assert len(mock_reload.mock_calls) == 1


async def test_options_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test options flow handles connection errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 1883,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_victron_hub")
async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test successful reauthentication flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: 42,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new-username"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    assert mock_config_entry.data[CONF_UPDATE_FREQUENCY_SECONDS] == 42


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test reauthentication flow handles connection errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_victron_hub.return_value.connect.side_effect = CannotConnectError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test recovery from error
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test reauthentication flow handles unknown errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    mock_victron_hub.return_value.connect.side_effect = Exception("Test error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test reauthentication flow handles authentication errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Invalid credentials"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "wrong-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Test recovery with correct credentials
    mock_victron_hub.return_value.connect.side_effect = None
    mock_victron_hub.return_value.installation_id = MOCK_INSTALLATION_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "correct-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_ssdp_flow_unknown_error(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test SSDP discovery flow handles unknown errors in auth step."""
    # First, trigger auth error to get to the auth step
    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Authentication required"
    )

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

    # Should show auth form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_auth"

    # Now trigger unknown error during auth
    mock_victron_hub.return_value.connect.side_effect = Exception("Unknown error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "test-user",
            CONF_PASSWORD: "test-pass",
        },
    )

    # Should show error in auth form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ssdp_auth"
    assert result["errors"] == {"base": "unknown"}


async def test_options_flow_invalid_auth(
    hass: HomeAssistant, mock_victron_hub: MagicMock
) -> None:
    """Test options flow handles authentication errors."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_INSTALLATION_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    mock_victron_hub.return_value.connect.side_effect = AuthenticationError(
        "Invalid auth"
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.200",
            CONF_PORT: 1883,
            CONF_USERNAME: "wrong-user",
            CONF_PASSWORD: "wrong-pass",
            CONF_SSL: False,
            CONF_UPDATE_FREQUENCY_SECONDS: DEFAULT_UPDATE_FREQUENCY_SECONDS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
