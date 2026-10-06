"""Test the Airobot config flow."""

from unittest.mock import AsyncMock, patch

from pyairobotmodbus.exceptions import (
    AirobotConnectionError as VUConnectionError,
    AirobotError as VUError,
    AirobotReadError as VUReadError,
    AirobotTimeoutError as VUTimeoutError,
)
from pyairobotmodbus.models import AirobotIdentity
from pyairobotrest.exceptions import (
    AirobotAuthError,
    AirobotConnectionError,
    AirobotError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.airobot.const import (
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_THERMOSTAT,
    DEVICE_TYPE_VENTILATION,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_USERNAME: "T01A1B2C3",
    CONF_PASSWORD: "test-password",
}

TEST_VU_INPUT = {
    CONF_HOST: "192.168.1.200",
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
) -> None:
    """Test user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "thermostat"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "thermostat"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"] == {
        **TEST_USER_INPUT,
        CONF_DEVICE_TYPE: DEVICE_TYPE_THERMOSTAT,
    }
    assert result["result"].unique_id == "T01A1B2C3"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (AirobotAuthError("Authentication failed"), "invalid_auth"),
        (AirobotConnectionError("Connection failed"), "cannot_connect"),
        (AirobotError("Generic error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test we handle various errors in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "thermostat"},
    )
    assert result["type"] is FlowResultType.FORM

    mock_airobot_client.get_settings.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    mock_airobot_client.get_settings.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"] == {
        **TEST_USER_INPUT,
        CONF_DEVICE_TYPE: DEVICE_TYPE_THERMOSTAT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate detection."""
    mock_config_entry.add_to_hass(hass)

    # Try to configure the same device again
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "thermostat"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_ventilation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
) -> None:
    """Test user flow for ventilation unit."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "ventilation"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ventilation"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_VU_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airobot Ventilation"
    assert result["data"] == {
        **TEST_VU_INPUT,
        CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    # The MAC read from the unit matches the unique ID DHCP discovery assigns
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_ventilation_without_identity(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
) -> None:
    """Test firmware without the identity registers is keyed by host."""
    mock_vu_client.async_get_identity.side_effect = VUReadError("Illegal address")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "ventilation"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_VU_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **TEST_VU_INPUT,
        CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
    }
    assert result["result"].unique_id is None


async def test_ventilation_link_settings_conflict(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
) -> None:
    """Test a unit held over different Modbus link settings can't connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "ventilation"},
    )

    with patch(
        "homeassistant.components.airobot.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError("In use with different link settings"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_VU_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recovers once the conflicting holder releases the unit
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_VU_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (VUConnectionError("Connection failed"), "cannot_connect"),
        (VUTimeoutError("Timeout"), "cannot_connect"),
        (VUError("Generic error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_ventilation_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test we handle various errors in ventilation flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "ventilation"},
    )
    assert result["type"] is FlowResultType.FORM

    mock_vu_client.async_get_data.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_VU_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_vu_client.async_get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_VU_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airobot Ventilation"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ventilation_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate detection for ventilation unit."""
    # Manually added entries are matched on host
    mock_vu_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **TEST_VU_INPUT,
            CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
        },
        title="Airobot Ventilation",
    )
    mock_vu_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "ventilation"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_VU_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ventilation_duplicate_mac(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test a configured unit found at a new address updates the host."""
    mock_vu_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "ventilation"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.201"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_vu_config_entry.data[CONF_HOST] == "192.168.1.201"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery(
    hass: HomeAssistant, mock_airobot_client: AsyncMock
) -> None:
    """Test DHCP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="b8d61aabcdef",
            hostname="airobot-thermostat-t01a1b2c3",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    assert result["description_placeholders"] == {
        "host": "192.168.1.100",
        "device_id": "T01A1B2C3",
    }

    # Complete the flow by providing password only
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_USERNAME] == "T01A1B2C3"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_MAC] == "b8d61aabcdef"
    assert result["data"][CONF_DEVICE_TYPE] == DEVICE_TYPE_THERMOSTAT
    assert result["result"].unique_id == "T01A1B2C3"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (AirobotAuthError("Invalid credentials"), "invalid_auth"),
        (AirobotConnectionError("Connection failed"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airobot_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test DHCP discovery with error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.100",
            macaddress="aabbccddeeff",
            hostname="airobot-thermostat-t01d4e5f6",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    mock_airobot_client.get_statuses.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "wrong"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_airobot_client.get_statuses.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "test-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Thermostat"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_duplicate(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery with duplicate device."""
    mock_config_entry.add_to_hass(hass)

    # DHCP discovers the same device with potentially different IP
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.101",  # Different IP
            macaddress="b8d61aabcdef",  # Same MAC
            hostname="airobot-thermostat-t01a1b2c3",  # Same hostname = same device_id
        ),
    )
    await hass.async_block_till_done()

    # Should abort immediately since device_id extracted from
    # hostname matches existing entry
    # and update the IP address
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the IP was updated in the existing entry
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"


async def test_dhcp_discovery_ventilation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
) -> None:
    """Test DHCP discovery for ventilation unit."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.200",
            macaddress="aabbccddeeff",
            hostname="airobot-ventilation",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vu_dhcp_confirm"
    assert result["description_placeholders"] == {
        "host": "192.168.1.200",
    }

    # Confirm the discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airobot Ventilation"
    assert result["data"][CONF_HOST] == "192.168.1.200"
    assert result["data"][CONF_DEVICE_TYPE] == DEVICE_TYPE_VENTILATION
    assert result["data"][CONF_MAC] == "aa:bb:cc:dd:ee:ff"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (VUError("Connection failed"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_dhcp_discovery_ventilation_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test DHCP discovery for ventilation unit with error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.200",
            macaddress="aabbccddeeff",
            hostname="airobot-ventilation",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "vu_dhcp_confirm"

    mock_vu_client.async_get_data.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_vu_client.async_get_data.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Airobot Ventilation"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_ventilation_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery for ventilation unit with duplicate MAC."""
    mock_vu_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.201",  # Different IP
            macaddress="aabbccddeeff",  # Same MAC
            hostname="airobot-ventilation",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the IP was updated
    assert mock_vu_config_entry.data[CONF_HOST] == "192.168.1.201"


async def test_dhcp_discovery_ventilation_manual_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
) -> None:
    """Test DHCP discovery aborts for a manually added ventilation unit."""
    # Manually added entries have no unique ID, only connection data
    vu_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            **TEST_VU_INPUT,
            CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
        },
        title="Airobot Ventilation",
    )
    vu_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.200",
            macaddress="aabbccddeeff",
            hostname="airobot-ventilation",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # The manual entry is upgraded with the discovered MAC so future
    # IP changes are tracked through the unique ID
    assert vu_entry.unique_id == "aa:bb:cc:dd:ee:ff"
    assert vu_entry.data[CONF_MAC] == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    # Trigger reauthentication
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["username"] == "T01A1B2C3"
    assert result["description_placeholders"]["host"] == "192.168.1.100"

    # Provide new password
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (AirobotAuthError("Invalid credentials"), "invalid_auth"),
        (AirobotConnectionError("Connection failed"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error_base: str,
) -> None:
    """Test reauthentication flow with errors."""
    mock_config_entry.add_to_hass(hass)

    # Trigger reauthentication
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # First attempt with error
    mock_airobot_client.get_statuses.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_airobot_client.get_statuses.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)

    # Trigger reconfiguration
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Update configuration (e.g., new IP address and password)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_USERNAME: "T01A1B2C3",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.data[CONF_USERNAME] == "T01A1B2C3"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_wrong_device(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with wrong device."""
    mock_config_entry.add_to_hass(hass)

    # Trigger reconfiguration
    result = await mock_config_entry.start_reconfigure_flow(hass)

    # Try to reconfigure with a different device ID
    mock_airobot_client.get_settings.return_value.device_name = "Different Device"
    mock_airobot_client.get_statuses.return_value.device_id = "T01DIFFERENT"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_USERNAME: "T01DIFFERENT",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (AirobotAuthError("Invalid credentials"), "invalid_auth"),
        (AirobotConnectionError("Connection failed"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_airobot_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error_base: str,
) -> None:
    """Test reconfiguration flow with errors."""
    mock_config_entry.add_to_hass(hass)

    # Trigger reconfiguration
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # First attempt with error
    mock_airobot_client.get_statuses.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_USERNAME: "T01A1B2C3",
            CONF_PASSWORD: "wrong-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_airobot_client.get_statuses.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_USERNAME: "T01A1B2C3",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reconfigure_ventilation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow for ventilation unit."""
    mock_vu_config_entry.add_to_hass(hass)

    result = await mock_vu_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_ventilation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.201"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_vu_config_entry.data[CONF_HOST] == "192.168.1.201"


async def test_reconfigure_ventilation_conflict(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test the ventilation reconfigure flow rejects a configured device."""
    mock_vu_config_entry.add_to_hass(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.201",
            CONF_DEVICE_TYPE: DEVICE_TYPE_VENTILATION,
        },
        title="Airobot Ventilation",
    )
    other_entry.add_to_hass(hass)

    result = await mock_vu_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.201"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_ventilation_wrong_unit(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring to a different unit is rejected."""
    mock_vu_config_entry.add_to_hass(hass)
    mock_vu_client.async_get_identity.return_value = AirobotIdentity(
        serial_number="07654321", mac_address="11:22:33:44:55:66"
    )

    result = await mock_vu_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.201"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_ventilation_unit"
    assert mock_vu_config_entry.data[CONF_HOST] == "192.168.1.200"


async def test_reauth_ventilation_unsupported(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts for ventilation units."""
    mock_vu_config_entry.add_to_hass(hass)

    result = await mock_vu_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_unsupported"


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (VUConnectionError("Connection failed"), "cannot_connect"),
        (VUTimeoutError("Timeout"), "cannot_connect"),
        (Exception("Unknown error"), "unknown"),
    ],
)
async def test_reconfigure_ventilation_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_vu_client: AsyncMock,
    mock_vu_config_entry: MockConfigEntry,
    exception: Exception,
    error_base: str,
) -> None:
    """Test reconfiguration flow for ventilation unit with errors."""
    mock_vu_config_entry.add_to_hass(hass)

    result = await mock_vu_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_ventilation"

    mock_vu_client.async_get_data.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.201"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Recover from error
    mock_vu_client.async_get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.201"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_vu_config_entry.data[CONF_HOST] == "192.168.1.201"
