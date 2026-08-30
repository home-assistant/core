"""Test the Mammotion Luba config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError
from bleak.backends.device import BLEDevice
import pytest

from homeassistant import config_entries
from homeassistant.components.mammotion.const import (
    CONF_ACCOUNT_ID,
    CONF_ACCOUNTNAME,
    CONF_BLE_DEVICES,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


def _get_mock_device(name="Luba-ABC123", address="AA:BB:CC:DD:EE:FF"):
    device = MagicMock(spec=BLEDevice)
    device.name = name
    device.address = address
    return device


def _get_discovery_info(name="Luba-ABC123", address="aa:bb:cc:dd:ee:ff"):
    discovery_info = MagicMock()
    discovery_info.name = name
    discovery_info.address = address.upper()
    return discovery_info


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_discovery_success(hass: HomeAssistant) -> None:
    """Test successful bluetooth discovery flow."""
    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "wifi"

    mock_http = MagicMock()
    mock_http.login_info.userInformation.userAccount = "user123"
    mock_http.login_v2 = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "user@example.com",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "user@example.com"
    assert result2["data"] == {
        CONF_ACCOUNTNAME: "user@example.com",
        CONF_PASSWORD: "password",
        CONF_ACCOUNT_ID: "user123",
        CONF_BLE_DEVICES: {"Luba-ABC123": "aa:bb:cc:dd:ee:ff"},
    }


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery aborts if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNT_ID: "user123"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_not_supported(hass: HomeAssistant) -> None:
    """Test discovery aborts if device name is not supported."""
    discovery_info = _get_discovery_info(name="Unknown-Device")
    device = _get_mock_device(name="Unknown-Device")

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_bluetooth_discovery_no_device(hass: HomeAssistant) -> None:
    """Test discovery aborts if device is None (no longer present)."""
    discovery_info = _get_discovery_info()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_longer_present"


async def test_user_step_pick_discovery(hass: HomeAssistant) -> None:
    """Test user step picking a discovered device."""
    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with (
        patch(
            "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
            return_value=[discovery_info],
        ),
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=device,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_mammotion = MagicMock()
    mock_mammotion.login_v2 = AsyncMock()
    mock_mammotion.login_info.userInformation.userAccount = "user123"

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_mammotion,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: "AA:BB:CC:DD:EE:FF"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"


async def test_user_step_manual_entry(hass: HomeAssistant) -> None:
    """Test user step with manual entry."""
    device = _get_mock_device()

    mock_mammotion = MagicMock()
    mock_mammotion.login_v2 = AsyncMock()
    mock_mammotion.login_info.userInformation.userAccount = "user123"

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=device,
        ),
        patch(
            "homeassistant.components.mammotion.config_flow.MammotionHTTP",
            return_value=mock_mammotion,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data={}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "wifi"


async def test_user_step_no_discovery(hass: HomeAssistant) -> None:
    """Test user step with no discovered devices goes to wifi."""
    with patch(
        "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "wifi"


async def test_wifi_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test wifi step returns error on invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_http = MagicMock()
    mock_http.login_info = None
    mock_http.login_v2 = AsyncMock(return_value=None)

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "user@example.com",
                CONF_PASSWORD: "wrong",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_wifi_step_connection_error(hass: HomeAssistant) -> None:
    """Test wifi step returns error on connection issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_http = MagicMock()
    mock_http.login_v2 = AsyncMock(side_effect=ClientConnectionError("Conn Err"))

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "user@example.com",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "wifi"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNTNAME: "old@example.com", CONF_PASSWORD: "old_password"},
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_http = MagicMock()
    mock_http.login_v2 = AsyncMock(return_value=None)
    mock_http.login_info.userInformation.userAccount = "user123"

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "new@example.com",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.data[CONF_ACCOUNTNAME] == "new@example.com"
    assert entry.data[CONF_PASSWORD] == "new_password"
    assert entry.data[CONF_ACCOUNT_ID] == "user123"


async def test_reconfigure_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test reconfiguration flow shows an error on invalid credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNTNAME: "old@example.com", CONF_PASSWORD: "old_password"},
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_http = MagicMock()
    mock_http.login_v2 = AsyncMock(return_value=None)
    mock_http.login_info = None

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "new@example.com",
                CONF_PASSWORD: "wrong",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {"base": "invalid_auth"}

    assert entry.data[CONF_ACCOUNTNAME] == "old@example.com"


async def test_reconfigure_flow_account_mismatch(hass: HomeAssistant) -> None:
    """Test reconfiguration flow aborts when a different account is used."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNTNAME: "old@example.com", CONF_PASSWORD: "old_password"},
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_http = MagicMock()
    mock_http.login_v2 = AsyncMock(return_value=None)
    mock_http.login_info.userInformation.userAccount = "other_user"

    with patch(
        "homeassistant.components.mammotion.config_flow.MammotionHTTP",
        return_value=mock_http,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNTNAME: "other@example.com",
                CONF_PASSWORD: "password",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "unique_id_mismatch"

    assert entry.data[CONF_ACCOUNTNAME] == "old@example.com"


async def test_bluetooth_discovery_update_existing_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test bluetooth discovery updates existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNT_ID: "user123"},
        unique_id="user123",
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "Luba-ABC123")},
        connections=set(),
    )

    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    device_entry = device_registry.async_get(device_entry.id)
    assert (dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff") in device_entry.connections


async def test_bluetooth_step_no_discovery_info(hass: HomeAssistant) -> None:
    """Test bluetooth step with no discovery info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=None,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_filtering(hass: HomeAssistant) -> None:
    """Test user step filters discovered devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
    )

    entry.add_to_hass(hass)

    discovery_info_configured = _get_discovery_info(
        name="existing entry", address="AA:BB:CC:DD:EE:FF"
    )
    discovery_info_unsupported = _get_discovery_info(
        name="Unsupported", address="11:22:33:44:55:66"
    )
    discovery_info_valid = _get_discovery_info(
        name="Luba-NEW", address="99:88:77:66:55:44"
    )

    device_valid = _get_mock_device(name="Luba-NEW", address="99:88:77:66:55:44")

    with (
        patch(
            "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
            return_value=[
                discovery_info_configured,
                discovery_info_unsupported,
                discovery_info_valid,
            ],
        ),
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=device_valid,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_bluetooth_confirm_race_condition(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test bluetooth confirm step race condition where device is configured during flow."""
    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNT_ID: "user123", CONF_BLE_DEVICES: {}},
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "Luba-ABC123")},
        connections={(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")},
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=device,
        ),
        patch(
            "homeassistant.helpers.device_registry.async_entries_for_config_entry",
            side_effect=[[], [device_entry]],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_skip_no_account_id(hass: HomeAssistant) -> None:
    """Test bluetooth discovery skips entries without account ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},  # No account ID
        unique_id="user123",
    )
    entry.add_to_hass(hass)

    discovery_info = _get_discovery_info()
    device = _get_mock_device()

    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=discovery_info,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


@pytest.mark.parametrize(
    ("stored_connections", "stored_ble_devices", "expect_reload"),
    [
        pytest.param(set(), {}, True, id="new_ble_address_reloads_once"),
        pytest.param(
            {(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")},
            {},
            False,
            id="known_address_missing_from_entry_data",
        ),
        pytest.param(
            {(dr.CONNECTION_BLUETOOTH, "aa:bb:cc:dd:ee:ff")},
            {"Luba-ABC123": "aa:bb:cc:dd:ee:ff"},
            False,
            id="known_address_already_in_entry_data",
        ),
    ],
)
async def test_bluetooth_discovery_only_reloads_for_new_address(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    stored_connections: set[tuple[str, str]],
    stored_ble_devices: dict[str, str],
    expect_reload: bool,
) -> None:
    """Test an advertisement for a known address does not reload a loaded entry.

    A reload stands up a second client alongside the running one, and the two
    MQTT sessions share a client_id, so the broker rejects both.  Writing
    CONF_BLE_DEVICES must therefore not trigger a reload of its own — the
    device-registry merge above already schedules the single one a genuinely
    new address needs.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNT_ID: "user123", CONF_BLE_DEVICES: stored_ble_devices},
        unique_id="user123",
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "Luba-ABC123")},
        connections=stored_connections,
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=_get_mock_device(),
        ),
        patch.object(
            hass.config_entries, "async_schedule_reload"
        ) as mock_schedule_reload,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=_get_discovery_info(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert (mock_schedule_reload.call_count > 0) is expect_reload


async def test_user_step_does_not_reload_loaded_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test listing candidates never reloads an entry that already owns a mower."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCOUNT_ID: "user123"},
        unique_id="user123",
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "Luba-ABC123")},
        connections=set(),
    )

    with (
        patch(
            "homeassistant.components.mammotion.config_flow.async_discovered_service_info",
            return_value=[_get_discovery_info()],
        ),
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=_get_mock_device(),
        ),
        patch.object(
            hass.config_entries, "async_schedule_reload"
        ) as mock_schedule_reload,
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    mock_schedule_reload.assert_not_called()


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth updates the password and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.mammotion.config_flow.MammotionHTTP"
        ) as mock_http,
        patch(
            "homeassistant.components.mammotion.async_setup_entry", return_value=True
        ),
    ):
        mock_http.return_value.login_v2 = AsyncMock()
        mock_http.return_value.login_info.userInformation.userAccount = "user123"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
