"""Tests for the Specialized Turbo config flow."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

from bleak import BleakError
import pytest
from specialized_turbo import (
    DecryptionError,
    EncryptionKeyProviderError,
    EncryptionKeyRequiredError,
    IdentificationError,
)
from specialized_turbo.cloud import CloudAuthenticationError, CloudRequestError

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.specialized_turbo.const import (
    CONF_HMI_HARDWARE,
    CONF_HMI_SERIAL,
    CONF_KEY_SOURCE,
    CONF_WRAPPED_KEY,
    DOMAIN,
    KEY_SOURCE_ACCOUNT,
    KEY_SOURCE_MANUAL,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    ENCRYPTED_SERVICE_INFO,
    MOCK_ADDRESS,
    MOCK_ADDRESS_FORMATTED,
    MOCK_TCU1_ADDRESS,
    NAME_ONLY_SERVICE_INFO,
    TCU1_SERVICE_INFO,
    TCX_SERVICE_INFO,
    MockLibrary,
    make_service_info,
    make_wrapped_key,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def _choose_key_source(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    next_step_id: str,
) -> ConfigFlowResult:
    """Choose an encryption key source from the menu."""
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "key_source"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": next_step_id},
    )


async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test Bluetooth discovery validates the connection and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SPECIALIZED"
    assert result["data"] == {CONF_ADDRESS: MOCK_ADDRESS}
    assert result["result"].unique_id == MOCK_ADDRESS_FORMATTED
    mock_library.connection.connect.assert_awaited_once()
    mock_library.connection.disconnect.assert_awaited_once()


async def test_config_flow_uses_managed_ble_client(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test the library client factory uses bleak_retry_connector."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    client_factory = mock_library.connection_constructor.call_args.kwargs[
        "client_factory"
    ]
    client = MagicMock()
    disconnected_callback = MagicMock()

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.establish_connection",
        new_callable=AsyncMock,
        return_value=client,
    ) as establish_connection:
        result_client = await client_factory(
            TCX_SERVICE_INFO.device,
            disconnected_callback,
        )

    assert result_client is client
    establish_connection.assert_awaited_once_with(
        ANY,
        TCX_SERVICE_INFO.device,
        MOCK_ADDRESS,
        disconnected_callback=disconnected_callback,
    )


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test Bluetooth discovery aborts for an existing bike."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_tcu1(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test Bluetooth discovery for a TCU1 bike."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCU1_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: MOCK_TCU1_ADDRESS}
    bike_info = mock_library.connection_constructor.call_args.kwargs["bike_info"]
    assert bike_info.ble_profile is not None


@pytest.mark.parametrize(
    "error",
    [
        BleakError("failed"),
        IdentificationError("failed"),
        TimeoutError(),
        RuntimeError("failed"),
        ValueError("failed"),
    ],
)
async def test_bluetooth_connection_errors(
    hass: HomeAssistant,
    mock_library: MockLibrary,
    error: Exception,
) -> None:
    """Test connection errors remain on the confirmation form."""
    mock_library.connection.connect.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_library.connection.disconnect.assert_awaited_once()

    mock_library.connection.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_device_unavailable(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test confirmation fails when the bike is no longer discoverable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=TCX_SERVICE_INFO,
    )

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_library.connection.connect.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_library.connection.connect.assert_awaited_once()


async def test_bluetooth_key_required_without_metadata(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test a late encryption requirement is reported without crashing the flow."""
    mock_library.connection.connect.side_effect = EncryptionKeyRequiredError("missing")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NAME_ONLY_SERVICE_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "key_unavailable"}

    mock_library.connection.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_encrypted_account_setup_uses_managed_http_client(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test account setup stores only the wrapped key and HMI identifiers."""
    wrapped_key = make_wrapped_key()
    cloud = MagicMock()
    cloud.login = AsyncMock()
    cloud.get_wrapped_key = AsyncMock(return_value=wrapped_key)
    http_client = MagicMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "account")
    assert result["step_id"] == "account"

    with (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.get_async_client",
            return_value=http_client,
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.SpecializedCloudClient",
            return_value=cloud,
        ) as cloud_constructor,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "rider@example.com",
                CONF_PASSWORD: "secret",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ADDRESS: MOCK_ADDRESS,
        CONF_HMI_HARDWARE: "B.3.3",
        CONF_HMI_SERIAL: "80005338",
        CONF_KEY_SOURCE: KEY_SOURCE_ACCOUNT,
        CONF_WRAPPED_KEY: wrapped_key,
    }
    cloud_constructor.assert_called_once_with(client=http_client)
    cloud.login.assert_awaited_once_with("rider@example.com", "secret")
    cloud.get_wrapped_key.assert_awaited_once_with(
        hmi_hardware="B.3.3",
        hmi_serial="80005338",
    )
    mock_library.connection.connect.assert_awaited_once()


@pytest.mark.parametrize(
    ("method_name", "error", "expected_error"),
    [
        ("login", CloudAuthenticationError("failed"), "invalid_auth"),
        ("get_wrapped_key", CloudRequestError("failed"), "key_unavailable"),
    ],
)
async def test_encrypted_account_errors(
    hass: HomeAssistant,
    mock_library: MockLibrary,
    method_name: str,
    error: Exception,
    expected_error: str,
) -> None:
    """Test account authentication and key retrieval errors."""
    cloud = MagicMock()
    cloud.login = AsyncMock()
    cloud.get_wrapped_key = AsyncMock(return_value=make_wrapped_key())
    getattr(cloud, method_name).side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "account")

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.SpecializedCloudClient",
        return_value=cloud,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "rider@example.com", CONF_PASSWORD: "secret"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}
        mock_library.connection.connect.assert_not_awaited()

        getattr(cloud, method_name).side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "rider@example.com", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "error",
    [
        DecryptionError("stale"),
        EncryptionKeyProviderError("invalid"),
        EncryptionKeyRequiredError("missing"),
    ],
)
async def test_encrypted_account_key_errors(
    hass: HomeAssistant,
    mock_library: MockLibrary,
    error: Exception,
) -> None:
    """Test key-specific account failures recover on the same form."""
    cloud = MagicMock()
    cloud.login = AsyncMock()
    cloud.get_wrapped_key = AsyncMock(return_value=make_wrapped_key())
    mock_library.connection.connect.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "account")

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.SpecializedCloudClient",
        return_value=cloud,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "rider@example.com", CONF_PASSWORD: "secret"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "key_unavailable"}

        mock_library.connection.connect.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "rider@example.com", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_encrypted_account_key_fails_connection(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test an account key must complete the bike identification handshake."""
    cloud = MagicMock()
    cloud.login = AsyncMock()
    cloud.get_wrapped_key = AsyncMock(return_value=make_wrapped_key())
    mock_library.connection.connect.side_effect = IdentificationError("failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "account")

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.SpecializedCloudClient",
        return_value=cloud,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "rider@example.com", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_library.connection.connect.side_effect = None
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.SpecializedCloudClient",
        return_value=cloud,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "rider@example.com", CONF_PASSWORD: "secret"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_encrypted_manual_key_setup(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test manual wrapped-key setup and validation."""
    wrapped_key = make_wrapped_key()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "manual_key")
    assert result["step_id"] == "manual_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: "invalid"},
    )
    assert result["errors"] == {"base": "invalid_wrapped_key"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: f" {wrapped_key} "},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_KEY_SOURCE] == KEY_SOURCE_MANUAL
    assert result["data"][CONF_WRAPPED_KEY] == wrapped_key
    mock_library.connection.connect.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        DecryptionError("stale"),
        EncryptionKeyProviderError("invalid"),
        EncryptionKeyRequiredError("missing"),
    ],
)
async def test_manual_key_rejected_by_bike(
    hass: HomeAssistant,
    mock_library: MockLibrary,
    error: Exception,
) -> None:
    """Test a wrapped key rejected by the bike remains on the form."""
    mock_library.connection.connect.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "manual_key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: make_wrapped_key()},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_wrapped_key"}

    mock_library.connection.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: make_wrapped_key()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_key_connection_failure_recovers(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test manual key setup recovers after an identification failure."""
    mock_library.connection.connect.side_effect = IdentificationError("failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=ENCRYPTED_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    result = await _choose_key_source(hass, result, "manual_key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: make_wrapped_key()},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_library.connection.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: make_wrapped_key()},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test user setup with a discovered bike."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[TCX_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MOCK_ADDRESS},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: MOCK_ADDRESS}
    mock_library.connection.connect.assert_awaited_once()


@pytest.mark.parametrize(
    "service_info",
    [TCU1_SERVICE_INFO, NAME_ONLY_SERVICE_INFO],
    ids=["tcu1", "name_only"],
)
async def test_user_flow_discovers_supported_variants(
    hass: HomeAssistant,
    mock_library: MockLibrary,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test manual setup discovers TCU1 and name-only WSBC bikes."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: service_info.address},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == service_info.name
    mock_library.connection.connect.assert_awaited_once()


async def test_user_flow_selects_encryption_source_after_bike(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test an encrypted user flow continues from the key-source menu."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[ENCRYPTED_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert CONF_KEY_SOURCE not in result["data_schema"].schema

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MOCK_ADDRESS},
    )

    result = await _choose_key_source(hass, result, "manual_key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: make_wrapped_key()},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_library.connection.connect.assert_awaited_once()


@pytest.mark.parametrize(
    "service_infos",
    [
        [],
        [
            make_service_info(
                name="Other device",
                address="AA:BB:CC:DD:EE:FF",
                manufacturer_data={},
            )
        ],
    ],
    ids=["none", "unsupported"],
)
async def test_user_flow_no_supported_devices(
    hass: HomeAssistant,
    service_infos: list[BluetoothServiceInfoBleak],
) -> None:
    """Test user setup aborts when no supported bikes are available."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=service_infos,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_filters_configured_bike(hass: HomeAssistant) -> None:
    """Test configured bikes are excluded from manual setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[TCX_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_reauth_adds_manual_key(
    hass: HomeAssistant,
    mock_library: MockLibrary,
) -> None:
    """Test reauthentication updates an encrypted entry."""
    wrapped_key = make_wrapped_key()
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_HMI_HARDWARE: "B.3.3",
            CONF_HMI_SERIAL: "80005338",
        },
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    result = await _choose_key_source(hass, result, "manual_key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: wrapped_key},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_WRAPPED_KEY] == wrapped_key
    mock_library.connection.connect.assert_awaited_once()


async def test_reconfigure_replaces_key(
    hass: HomeAssistant,
    encrypted_config_entry: MockConfigEntry,
    mock_library: MockLibrary,
) -> None:
    """Test reconfiguration replaces the existing key."""
    encrypted_config_entry.add_to_hass(hass)
    new_wrapped_key = make_wrapped_key(
        bytes.fromhex("ffeeddccbbaa99887766554433221100")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": encrypted_config_entry.entry_id,
        },
    )

    result = await _choose_key_source(hass, result, "manual_key")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_WRAPPED_KEY: new_wrapped_key},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert encrypted_config_entry.data[CONF_KEY_SOURCE] == KEY_SOURCE_MANUAL
    assert encrypted_config_entry.data[CONF_WRAPPED_KEY] == new_wrapped_key
    mock_library.connection.connect.assert_awaited_once()


async def test_reconfigure_unencrypted_entry_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration is limited to encrypted entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_encrypted"
