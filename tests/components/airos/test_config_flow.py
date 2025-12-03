"""Test the Ubiquiti airOS config flow."""

from typing import Any
from unittest.mock import AsyncMock

from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDeviceConnectionError,
    AirOSEndpointError,
    AirOSKeyDataMissingError,
    AirOSListenerError,
)
import pytest
import voluptuous as vol

from homeassistant.components.airos.const import (
    DEFAULT_USERNAME,
    DOMAIN,
    HOSTNAME,
    IP_ADDRESS,
    MAC_ADDRESS,
    SECTION_ADVANCED_SETTINGS,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

NEW_PASSWORD = "new_password"
REAUTH_STEP = "reauth_confirm"
RECONFIGURE_STEP = "reconfigure"

MOCK_ADVANCED_SETTINGS = {
    CONF_SSL: True,
    CONF_VERIFY_SSL: False,
}

MOCK_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: DEFAULT_USERNAME,
    CONF_PASSWORD: "test-password",
    SECTION_ADVANCED_SETTINGS: MOCK_ADVANCED_SETTINGS,
}
MOCK_CONFIG_REAUTH = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: DEFAULT_USERNAME,
    CONF_PASSWORD: "wrong-password",
}

MOCK_DISC_DEV1 = {
    MAC_ADDRESS: "00:11:22:33:44:55",
    IP_ADDRESS: "192.168.1.100",
    HOSTNAME: "Test-Device-1",
}
MOCK_DISC_DEV2 = {
    MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
    IP_ADDRESS: "192.168.1.101",
    HOSTNAME: "Test-Device-2",
}
MOCK_DISC_EXISTS = {
    MAC_ADDRESS: "01:23:45:67:89:AB",
    IP_ADDRESS: "192.168.1.102",
    HOSTNAME: "Existing-Device",
}


async def test_manual_flow_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airos_client: AsyncMock,
    ap_fixture: dict[str, Any],
) -> None:
    """Test we get the user form and create the appropriate entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert "manual" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NanoStation 5AC ap name"
    assert result["result"].unique_id == "01:23:45:67:89:AB"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_entry(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
) -> None:
    """Test the form does not allow duplicate entries."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="01:23:45:67:89:AB",
        data=MOCK_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    flow_start = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    menu = await hass.config_entries.flow.async_configure(
        flow_start["flow_id"], {"next_step_id": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        menu["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AirOSConnectionAuthenticationError, "invalid_auth"),
        (AirOSConnectionSetupError, "cannot_connect"),
        (AirOSDeviceConnectionError, "cannot_connect"),
        (AirOSKeyDataMissingError, "key_data_missing"),
        (Exception, "unknown"),
    ],
)
async def test_form_exception_handling(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_airos_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle exceptions."""
    mock_airos_client.login.side_effect = exception

    flow_start = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    menu = await hass.config_entries.flow.async_configure(
        flow_start["flow_id"], {"next_step_id": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        menu["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_airos_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NanoStation 5AC ap name"
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_scenario(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauthentication."""
    mock_config_entry.add_to_hass(hass)

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == REAUTH_STEP

    mock_airos_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    # Always test resolution
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == NEW_PASSWORD


@pytest.mark.parametrize(
    ("reauth_exception", "expected_error"),
    [
        (AirOSConnectionAuthenticationError, "invalid_auth"),
        (AirOSDeviceConnectionError, "cannot_connect"),
        (AirOSKeyDataMissingError, "key_data_missing"),
        (Exception, "unknown"),
    ],
    ids=[
        "invalid_auth",
        "cannot_connect",
        "key_data_missing",
        "unknown",
    ],
)
async def test_reauth_flow_scenarios(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reauth_exception: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication from start (failure) to finish (success)."""
    mock_config_entry.add_to_hass(hass)

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == REAUTH_STEP

    mock_airos_client.login.side_effect = reauth_exception

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == REAUTH_STEP
    assert result["errors"] == {"base": expected_error}

    mock_airos_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == NEW_PASSWORD


async def test_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication failure when the unique ID changes."""
    mock_config_entry.add_to_hass(hass)

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    flow = flows[0]

    mock_airos_client.login.side_effect = None
    mock_airos_client.status.return_value.derived.mac = "FF:23:45:67:89:AB"

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_PASSWORD: NEW_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] != NEW_PASSWORD


async def test_successful_reconfigure(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reconfigure."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == RECONFIGURE_STEP

    user_input = {
        CONF_PASSWORD: NEW_PASSWORD,
        SECTION_ADVANCED_SETTINGS: {
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == NEW_PASSWORD
    assert updated_entry.data[SECTION_ADVANCED_SETTINGS][CONF_SSL] is True
    assert updated_entry.data[SECTION_ADVANCED_SETTINGS][CONF_VERIFY_SSL] is True

    assert updated_entry.data[CONF_HOST] == MOCK_CONFIG[CONF_HOST]
    assert updated_entry.data[CONF_USERNAME] == MOCK_CONFIG[CONF_USERNAME]


@pytest.mark.parametrize(
    ("reconfigure_exception", "expected_error"),
    [
        (AirOSConnectionAuthenticationError, "invalid_auth"),
        (AirOSDeviceConnectionError, "cannot_connect"),
        (AirOSKeyDataMissingError, "key_data_missing"),
        (Exception, "unknown"),
    ],
    ids=[
        "invalid_auth",
        "cannot_connect",
        "key_data_missing",
        "unknown",
    ],
)
async def test_reconfigure_flow_failure(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reconfigure_exception: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure from start (failure) to finish (success)."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )

    user_input = {
        CONF_PASSWORD: NEW_PASSWORD,
        SECTION_ADVANCED_SETTINGS: {
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    }

    mock_airos_client.login.side_effect = reconfigure_exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == RECONFIGURE_STEP
    assert result["errors"] == {"base": expected_error}

    mock_airos_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == NEW_PASSWORD


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_airos_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration failure when the unique ID changes."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    flow_id = result["flow_id"]

    mock_airos_client.status.return_value.derived.mac = "FF:23:45:67:89:AB"

    user_input = {
        CONF_PASSWORD: NEW_PASSWORD,
        SECTION_ADVANCED_SETTINGS: {
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    }

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data[CONF_PASSWORD] == MOCK_CONFIG[CONF_PASSWORD]
    assert (
        updated_entry.data[SECTION_ADVANCED_SETTINGS][CONF_SSL]
        == MOCK_CONFIG[SECTION_ADVANCED_SETTINGS][CONF_SSL]
    )


async def test_discover_flow_no_devices_found(
    hass: HomeAssistant, mock_discovery_method
) -> None:
    """Test discovery flow aborts when no devices are found."""
    mock_discovery_method.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_discover_flow_one_device_found(
    hass: HomeAssistant, mock_discovery_method, mock_airos_client, mock_setup_entry
) -> None:
    """Test discovery flow goes straight to credentials when one device is found."""
    mock_discovery_method.return_value = {MOCK_DISC_DEV1[MAC_ADDRESS]: MOCK_DISC_DEV1}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery"}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # With only one device, the flow should skip the select step and
    # go directly to configure_device.
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_device"
    assert result["description_placeholders"]["device_name"] == MOCK_DISC_DEV1[HOSTNAME]

    # Provide credentials and complete the flow
    mock_airos_client.status.return_value.derived.mac = MOCK_DISC_DEV1[MAC_ADDRESS]
    mock_airos_client.status.return_value.host.hostname = MOCK_DISC_DEV1[HOSTNAME]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "test-password",
            SECTION_ADVANCED_SETTINGS: MOCK_ADVANCED_SETTINGS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DISC_DEV1[HOSTNAME]
    assert result["data"][CONF_HOST] == MOCK_DISC_DEV1[IP_ADDRESS]


async def test_discover_flow_multiple_devices_found(
    hass: HomeAssistant, mock_discovery_method, mock_airos_client, mock_setup_entry
) -> None:
    """Test discovery flow with multiple devices found, requiring a selection step."""
    mock_discovery_method.return_value = {
        MOCK_DISC_DEV1[MAC_ADDRESS]: MOCK_DISC_DEV1,
        MOCK_DISC_DEV2[MAC_ADDRESS]: MOCK_DISC_DEV2,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert "discovery" in result["menu_options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery"}
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "discovery"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"

    expected_options = {
        MOCK_DISC_DEV1[MAC_ADDRESS]: (
            f"{MOCK_DISC_DEV1[HOSTNAME]} ({MOCK_DISC_DEV1[IP_ADDRESS]})"
        ),
        MOCK_DISC_DEV2[MAC_ADDRESS]: (
            f"{MOCK_DISC_DEV2[HOSTNAME]} ({MOCK_DISC_DEV2[IP_ADDRESS]})"
        ),
    }
    actual_options = result["data_schema"].schema[vol.Required(MAC_ADDRESS)].container
    assert actual_options == expected_options

    # Select one of the devices
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {MAC_ADDRESS: MOCK_DISC_DEV1[MAC_ADDRESS]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_device"
    assert result["description_placeholders"]["device_name"] == MOCK_DISC_DEV1[HOSTNAME]

    # Provide credentials and complete the flow
    mock_airos_client.status.return_value.derived.mac = MOCK_DISC_DEV1[MAC_ADDRESS]
    mock_airos_client.status.return_value.host.hostname = MOCK_DISC_DEV1[HOSTNAME]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "test-password",
            SECTION_ADVANCED_SETTINGS: MOCK_ADVANCED_SETTINGS,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DISC_DEV1[HOSTNAME]
    assert result["data"][CONF_HOST] == MOCK_DISC_DEV1[IP_ADDRESS]


async def test_discover_flow_with_existing_device(
    hass: HomeAssistant, mock_discovery_method, mock_airos_client
) -> None:
    """Test that discovery ignores devices that are already configured."""
    # Add a mock config entry for an existing device
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DISC_EXISTS[MAC_ADDRESS],
        data=MOCK_CONFIG,
    )
    mock_entry.add_to_hass(hass)

    # Mock discovery to find both a new device and the existing one
    mock_discovery_method.return_value = {
        MOCK_DISC_DEV1[MAC_ADDRESS]: MOCK_DISC_DEV1,
        MOCK_DISC_EXISTS[MAC_ADDRESS]: MOCK_DISC_EXISTS,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery"}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # The flow should proceed with only the new device
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_device"
    assert result["description_placeholders"]["device_name"] == MOCK_DISC_DEV1[HOSTNAME]


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (AirOSEndpointError, "detect_error"),
        (AirOSListenerError, "listen_error"),
        (Exception, "discovery_failed"),
    ],
)
async def test_discover_flow_discovery_exceptions(
    hass: HomeAssistant,
    mock_discovery_method,
    exception: Exception,
    reason: str,
) -> None:
    """Test discovery flow aborts on various discovery exceptions."""
    mock_discovery_method.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery"}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_configure_device_flow_exceptions(
    hass: HomeAssistant, mock_discovery_method, mock_airos_client
) -> None:
    """Test configure_device step handles authentication and connection exceptions."""
    mock_discovery_method.return_value = {MOCK_DISC_DEV1[MAC_ADDRESS]: MOCK_DISC_DEV1}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery"}
    )

    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "wrong-user",
            CONF_PASSWORD: "wrong-password",
            SECTION_ADVANCED_SETTINGS: MOCK_ADVANCED_SETTINGS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_airos_client.login.side_effect = AirOSDeviceConnectionError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: "some-password",
            SECTION_ADVANCED_SETTINGS: MOCK_ADVANCED_SETTINGS,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
