"""Test the OpenDisplay config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from opendisplay import (
    AuthenticationFailedError,
    AuthenticationRequiredError,
    BLEConnectionError,
    BLETimeoutError,
    OpenDisplayError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.opendisplay.const import CONF_ENCRYPTION_KEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import ENCRYPTION_KEY, NOT_OPENDISPLAY_SERVICE_INFO, VALID_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Prevent the integration from actually setting up after config flow."""
    with patch(
        "homeassistant.components.opendisplay.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via Bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenDisplay 1234"
    assert result["data"] == {}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_already_in_progress(hass: HomeAssistant) -> None:
    """Test discovery aborts when same device flow is in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("exception", "expected_reason"),
    [
        (BLEConnectionError("test"), "cannot_connect"),
        (BLETimeoutError("test"), "cannot_connect"),
        (OpenDisplayError("test"), "cannot_connect"),
        (RuntimeError("test"), "unknown"),
    ],
)
async def test_bluetooth_confirm_connection_error(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    exception: Exception,
    expected_reason: str,
) -> None:
    """Test confirm step aborts when connection fails before showing the form."""
    mock_opendisplay_device.__aenter__.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


async def test_bluetooth_confirm_ble_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test confirm step aborts when BLE device is not found."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=VALID_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_step_with_devices(hass: HomeAssistant) -> None:
    """Test user step with discovered devices."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenDisplay 1234"
    assert result["data"] == {}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step when no devices are discovered."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_filters_unsupported(hass: HomeAssistant) -> None:
    """Test user step filters out unsupported devices."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[NOT_OPENDISPLAY_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (BLEConnectionError("test"), "cannot_connect"),
        (BLETimeoutError("test"), "cannot_connect"),
        (OpenDisplayError("test"), "cannot_connect"),
        (RuntimeError("test"), "unknown"),
    ],
)
async def test_user_step_connection_error(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step handles connection and unexpected errors."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM

    mock_opendisplay_device.__aenter__.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_opendisplay_device.__aenter__.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user step aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    # Device is filtered out since it's already configured
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_bluetooth_discovery_encrypted_device(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
) -> None:
    """Test Bluetooth discovery prompts for key when device requires encryption."""
    mock_opendisplay_device.__aenter__.side_effect = [
        AuthenticationRequiredError("auth required"),
        mock_opendisplay_device,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENCRYPTION_KEY: ENCRYPTION_KEY}


async def test_bluetooth_discovery_encrypted_invalid_key_format(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
) -> None:
    """Test encryption_key step shows error on invalid key format."""
    mock_opendisplay_device.__aenter__.side_effect = [
        AuthenticationRequiredError("auth required"),
        mock_opendisplay_device,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["step_id"] == "encryption_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: "tooshort"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"
    assert result["errors"] == {CONF_ENCRYPTION_KEY: "invalid_key_format"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_discovery_encrypted_wrong_key(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
) -> None:
    """Test encryption_key step shows error on wrong key, then succeeds."""
    mock_opendisplay_device.__aenter__.side_effect = [
        AuthenticationRequiredError("auth required"),
        AuthenticationFailedError("wrong key"),
        mock_opendisplay_device,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["step_id"] == "encryption_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENCRYPTION_KEY: "invalid_auth"}

    mock_opendisplay_device.__aenter__.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENCRYPTION_KEY: ENCRYPTION_KEY}


async def test_user_step_encrypted_device(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
) -> None:
    """Test user step prompts for key when device requires encryption."""
    mock_opendisplay_device.__aenter__.side_effect = [
        AuthenticationRequiredError("auth required"),
        mock_opendisplay_device,
    ]

    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encryption_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENCRYPTION_KEY: ENCRYPTION_KEY}


async def test_reauth_update_key(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    mock_encrypted_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow updates the encryption key."""
    mock_encrypted_config_entry.add_to_hass(hass)
    new_key = "11223344556677881122334455667788"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_encrypted_config_entry.entry_id,
        },
        data=mock_encrypted_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: new_key},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_encrypted_config_entry.data[CONF_ENCRYPTION_KEY] == new_key


async def test_reauth_remove_key(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    mock_encrypted_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow removes the encryption key when left blank."""
    mock_encrypted_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_encrypted_config_entry.entry_id,
        },
        data=mock_encrypted_config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ""},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert CONF_ENCRYPTION_KEY not in mock_encrypted_config_entry.data


async def test_reauth_wrong_key(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    mock_encrypted_config_entry: MockConfigEntry,
) -> None:
    """Test reauth form shows error for wrong key, then succeeds."""
    mock_encrypted_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_encrypted_config_entry.entry_id,
        },
        data=mock_encrypted_config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    mock_opendisplay_device.__aenter__.side_effect = [
        AuthenticationFailedError("wrong key"),
        mock_opendisplay_device,
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENCRYPTION_KEY: "invalid_auth"}

    mock_opendisplay_device.__aenter__.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_invalid_key_format(
    hass: HomeAssistant,
    mock_encrypted_config_entry: MockConfigEntry,
) -> None:
    """Test reauth form shows error for a malformed encryption key."""
    mock_encrypted_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_encrypted_config_entry.entry_id,
        },
        data=mock_encrypted_config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ENCRYPTION_KEY: "notvalidhex!"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ENCRYPTION_KEY: "invalid_key_format"}
