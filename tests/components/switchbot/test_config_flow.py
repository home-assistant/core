"""Test the switchbot config flow."""

from collections.abc import Generator
from unittest.mock import ANY, Mock, patch

import pytest
from switchbot import (
    OAUTH_AUTHORIZE_URL,
    OAUTH_SCOPE,
    OAUTH_TOKEN_URL,
    SwitchbotAccountConnectionError,
    SwitchbotApiError,
    SwitchbotAuthenticationError,
)
from yarl import URL

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.switchbot.const import (
    CONF_CURTAIN_SPEED,
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    CONF_LOCK_NIGHTLATCH,
    CONF_RETRY_COUNT,
    OAUTH_CLIENT_ID,
)
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_IGNORE,
    SOURCE_USER,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from . import (
    LOCK_ULTRA_MAX_SERVICE_INFO,
    NOT_SWITCHBOT_INFO,
    USER_INPUT,
    WOCURTAIN_SERVICE_INFO,
    WOHAND_ENCRYPTED_SERVICE_INFO,
    WOHAND_SERVICE_ALT_ADDRESS_INFO,
    WOHAND_SERVICE_INFO,
    WOHAND_SERVICE_INFO_NOT_CONNECTABLE,
    WOLOCK_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO_NOT_CONNECTABLE,
    WORELAY_SWITCH_1PM_SERVICE_INFO,
    WOSENSORTH_SERVICE_INFO,
    init_integration,
    patch_async_setup_entry,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

DOMAIN = "switchbot"
OAUTH_ACCESS_TOKEN = "oauth-access-token"


@pytest.fixture
def mock_scanners_all_passive() -> Generator[None]:
    """Mock all scanners as passive mode."""
    mock_scanner = Mock()
    mock_scanner.current_mode = BluetoothScanningMode.PASSIVE
    with patch(
        "homeassistant.components.bluetooth.async_current_scanners",
        return_value=[mock_scanner],
    ):
        yield


async def _async_start_user_oauth(hass: HomeAssistant) -> ConfigFlowResult:
    """Start OAuth from the user menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "oauth_login"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "auth"
    return result


def _oauth_state(hass: HomeAssistant, flow_id: str) -> str:
    """Create the state generated for the fixed SwitchBot callback."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": config_entry_oauth2_flow.MY_AUTH_CALLBACK_PATH,
        },
    )


def test_oauth_production_configuration() -> None:
    """Test OAuth uses the SwitchBot production configuration."""
    assert OAUTH_CLIENT_ID == "RuCCpYJPMcuZsWOfupJQYmuIPr"
    assert OAUTH_AUTHORIZE_URL == "https://sp.oauth.switchbot.net"
    assert (
        OAUTH_TOKEN_URL == "https://account.api.switchbot.net/merchant/v1/oauth/token"
    )
    assert OAUTH_SCOPE == "api_login"


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOHAND_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_requires_password(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device that needs a password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOHAND_ENCRYPTED_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "abc123"},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot 923B"
    assert result["data"] == {
        CONF_ADDRESS: "798A8547-2A3D-C609-55FF-73FA824B923B",
        CONF_SENSOR_TYPE: "bot",
        CONF_PASSWORD: "abc123",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_encrypted_key(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a lock."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOLOCK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {}

    with patch(
        "switchbot.SwitchbotLock.verify_encryption_key",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "",
                CONF_ENCRYPTION_KEY: "",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {"base": "encryption_key_invalid"}

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lock EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_lock_ultra_max(hass: HomeAssistant) -> None:
    """Test discovery of an encrypted Lock Ultra Max."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=LOCK_ULTRA_MAX_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch("switchbot.SwitchbotLock.verify_encryption_key", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SENSOR_TYPE] == "lock_ultra_max"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_key(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a encrypted device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WORELAY_SWITCH_1PM_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {}

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotRelaySwitch.verify_encryption_key", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Relay Switch 1PM EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "relay_switch_1pm",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_encrypted_key_back_navigation(
    hass: HomeAssistant,
) -> None:
    """Test that resuming an abandoned encrypted_key flow resets to the method menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOLOCK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    # User selects encrypted_key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"

    # Simulate user closing dialog and re-opening: call the step with no input
    # (as HA does when resuming an in-progress flow)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=None
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    # User can now pick a method again and complete the flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_encrypted_auth_back_navigation(
    hass: HomeAssistant,
) -> None:
    """Test that resuming an abandoned encrypted_auth flow resets to the method menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOLOCK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    # User selects encrypted_auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"

    # Simulate user closing dialog and re-opening: call the step with no input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=None
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    # User can switch to encrypted_key and complete the flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_discovery_already_setup(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOHAND_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_not_switchbot(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not switchbot."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=NOT_SWITCHBOT_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_bluetooth_not_connectable(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth and its not connectable switchbot."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOHAND_SERVICE_INFO_NOT_CONNECTABLE,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_bluetooth_meter_pro_co2_not_connectable(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth for Meter Pro CO2 from a non-connectable source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOMETERTHPC_SERVICE_INFO_NOT_CONNECTABLE,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Meter Pro CO2 EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "hygrometer_co2",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wohand(hass: HomeAssistant) -> None:
    """Test the user initiated form with password and valid mac."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOHAND_SERVICE_INFO],
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.bluetooth.async_request_active_scan"
        ) as mock_request_active_scan,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None
    mock_request_active_scan.assert_awaited_once_with(hass)

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wohand_already_configured(hass: HomeAssistant) -> None:
    """Test the user initiated form with password and valid mac."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOHAND_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wohand_replaces_ignored(hass: HomeAssistant) -> None:
    """Test setting up a switchbot replaces an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id="aabbccddeeff", source=SOURCE_IGNORE
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOHAND_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wocurtain(hass: HomeAssistant) -> None:
    """Test the user initiated form with password and valid mac."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOCURTAIN_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Curtain EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_SENSOR_TYPE: "curtain",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wocurtain_or_bot(hass: HomeAssistant) -> None:
    """Test the user initiated form with valid address."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[
            NOT_SWITCHBOT_INFO,
            WOCURTAIN_SERVICE_INFO,
            WOHAND_SERVICE_ALT_ADDRESS_INFO,
            WOHAND_SERVICE_INFO_NOT_CONNECTABLE,
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"
    assert result["errors"] == {}

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Curtain EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_SENSOR_TYPE: "curtain",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wocurtain_or_bot_with_password(hass: HomeAssistant) -> None:
    """Test the user initiated form and valid address and a bot with a password."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[
            WOCURTAIN_SERVICE_INFO,
            WOHAND_ENCRYPTED_SERVICE_INFO,
            WOHAND_SERVICE_INFO_NOT_CONNECTABLE,
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: "798A8547-2A3D-C609-55FF-73FA824B923B"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "password"
    assert result2["errors"] is None

    with patch_async_setup_entry() as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_PASSWORD: "abc123"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Bot 923B"
    assert result3["data"] == {
        CONF_ADDRESS: "798A8547-2A3D-C609-55FF-73FA824B923B",
        CONF_PASSWORD: "abc123",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_single_bot_with_password(hass: HomeAssistant) -> None:
    """Test the user initiated form for a bot with a password."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOHAND_ENCRYPTED_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password"
    assert result["errors"] is None

    with patch_async_setup_entry() as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "abc123"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Bot 923B"
    assert result2["data"] == {
        CONF_ADDRESS: "798A8547-2A3D-C609-55FF-73FA824B923B",
        CONF_PASSWORD: "abc123",
        CONF_SENSOR_TYPE: "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_woencrypted_key(hass: HomeAssistant) -> None:
    """Test the user initiated form for a lock."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOLOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {}

    with patch(
        "switchbot.SwitchbotLock.verify_encryption_key",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "",
                CONF_ENCRYPTION_KEY: "",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {"base": "encryption_key_invalid"}

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lock EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_woencrypted_auth(hass: HomeAssistant) -> None:
    """Test the user initiated form for a lock."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOLOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {}

    with patch(
        "switchbot.SwitchbotLock.async_retrieve_encryption_key",
        side_effect=SwitchbotAuthenticationError("error from api"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {"base": "auth_failed"}
    assert "error from api" in result["description_placeholders"]["error_detail"]

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
        patch(
            "switchbot.SwitchbotLock.async_retrieve_encryption_key",
            return_value={
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lock EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_woencrypted_auth_switchbot_api_down(
    hass: HomeAssistant,
) -> None:
    """Test the user initiated form for a lock when the switchbot api is down."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOLOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {}

    with patch(
        "switchbot.SwitchbotLock.async_retrieve_encryption_key",
        side_effect=SwitchbotAccountConnectionError("Switchbot API down"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_error"
    assert result["description_placeholders"] == {"error_detail": "Switchbot API down"}


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_woencrypted_auth_unknown_error(
    hass: HomeAssistant,
) -> None:
    """Test the encrypted auth step shows unknown error for unexpected exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOLOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"

    with patch(
        "switchbot.SwitchbotLock.async_retrieve_encryption_key",
        side_effect=Exception("Unexpected network failure"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {"base": "unknown"}

    # Recover: re-submit with valid credentials and successful key retrieval
    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
        patch(
            "switchbot.SwitchbotLock.async_retrieve_encryption_key",
            return_value={
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user@example.com",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lock EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wolock_or_bot(hass: HomeAssistant) -> None:
    """Test the user initiated form for a lock."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[
            WOLOCK_SERVICE_INFO,
            WOHAND_SERVICE_ALT_ADDRESS_INFO,
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {}

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.verify_encryption_key",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lock EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_wosensor(hass: HomeAssistant) -> None:
    """Test the user initiated form with password and valid mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOSENSORTH_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] is None

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Meter EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_SENSOR_TYPE: "hygrometer",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_cloud_login(hass: HomeAssistant) -> None:
    """Test the cloud login flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_login"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"

    # Test successful cloud login
    with (
        patch(
            "homeassistant.components.switchbot.config_flow.fetch_cloud_devices",
            return_value=None,
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOHAND_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "testpass",
            },
        )

    # Should proceed to device selection with single device, so go to confirm
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Confirm device setup
    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_cloud_login_auth_failed(hass: HomeAssistant) -> None:
    """Test the cloud login flow with authentication failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_login"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"

    # Test authentication failure
    with patch(
        "homeassistant.components.switchbot.config_flow.fetch_cloud_devices",
        side_effect=SwitchbotAuthenticationError("Invalid credentials"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "wrongpass",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"
    assert result["errors"] == {"base": "auth_failed"}
    assert "Invalid credentials" in result["description_placeholders"]["error_detail"]


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_cloud_login_api_error(hass: HomeAssistant) -> None:
    """Test the cloud login flow with API error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_login"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"

    # Test API connection error
    with patch(
        "homeassistant.components.switchbot.config_flow.fetch_cloud_devices",
        side_effect=SwitchbotAccountConnectionError("API is down"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "testpass",
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_error"
    assert result["description_placeholders"] == {"error_detail": "API is down"}


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_cloud_login_unknown_error(hass: HomeAssistant) -> None:
    """Test the cloud login step shows unknown error for unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_login"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"

    with patch(
        "homeassistant.components.switchbot.config_flow.fetch_cloud_devices",
        side_effect=Exception("Unexpected network failure"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "testpass",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"
    assert result["errors"] == {"base": "unknown"}

    # Recover: re-submit with valid credentials and successful cloud login
    with (
        patch(
            "homeassistant.components.switchbot.config_flow.fetch_cloud_devices",
            return_value=None,
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOHAND_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "testpass",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_cloud_login_then_encrypted_device(hass: HomeAssistant) -> None:
    """Test cloud login followed by encrypted device setup using saved credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "cloud_login"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cloud_login"

    with (
        patch(
            "homeassistant.components.switchbot.config_flow.fetch_cloud_devices",
            return_value=None,
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOLOCK_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "testpass",
            },
        )

    # Should go to encrypted device choice menu
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    # Choose encrypted auth
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"

    # Simulate the user navigating away and re-opening the dialog.
    # The failed auto-auth cleared credentials, so calling with None now
    # redirects back to the method selection menu.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        None,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    # User selects encrypted_auth again and manually enters credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotLock.async_retrieve_encryption_key",
            return_value={
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        ),
        patch("switchbot.SwitchbotLock.verify_encryption_key", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "testpass",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Lock EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_no_devices(hass: HomeAssistant) -> None:
    """Test the user initiated form with password and valid mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOCURTAIN_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WOCURTAIN_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
        assert result["type"] is FlowResultType.FORM

    with patch_async_setup_entry() as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Curtain EEFF"
    assert result2["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_SENSOR_TYPE: "curtain",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        options={
            CONF_RETRY_COUNT: 10,
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 3,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RETRY_COUNT] == 3

    assert len(mock_setup_entry.mock_calls) == 2

    # Test changing of entry options.

    with patch_async_setup_entry() as mock_setup_entry:
        entry = await init_integration(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 6,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RETRY_COUNT] == 6

    assert len(mock_setup_entry.mock_calls) == 1

    assert entry.options[CONF_RETRY_COUNT] == 6


async def test_options_flow_lock_pro(hass: HomeAssistant) -> None:
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "lock_pro",
        },
        options={CONF_RETRY_COUNT: 10},
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    # Test Force night_latch should be disabled by default.
    with patch_async_setup_entry() as mock_setup_entry:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 3,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCK_NIGHTLATCH] is False

    assert len(mock_setup_entry.mock_calls) == 1

    # Test Set force night_latch to be enabled.

    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCK_NIGHTLATCH: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCK_NIGHTLATCH] is True

    assert len(mock_setup_entry.mock_calls) == 0

    assert entry.options[CONF_LOCK_NIGHTLATCH] is True


async def test_options_flow_curtain_speed(hass: HomeAssistant) -> None:
    """Test updating curtain speed option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "curtain",
        },
        options={CONF_RETRY_COUNT: 2, CONF_CURTAIN_SPEED: 255},
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch_async_setup_entry() as mock_setup_entry:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 4,
                CONF_CURTAIN_SPEED: 100,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RETRY_COUNT] == 4
    assert result["data"][CONF_CURTAIN_SPEED] == 100
    assert entry.options[CONF_CURTAIN_SPEED] == 100
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_worelay_switch_1pm_key(hass: HomeAssistant) -> None:
    """Test the user initiated form for a relay switch 1pm."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WORELAY_SWITCH_1PM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_key"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_key"
    assert result["errors"] == {}

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotRelaySwitch.verify_encryption_key", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Relay Switch 1PM EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "relay_switch_1pm",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_worelay_switch_1pm_auth(hass: HomeAssistant) -> None:
    """Test the user initiated form for a relay switch 1pm."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WORELAY_SWITCH_1PM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {}

    with patch(
        "switchbot.SwitchbotRelaySwitch.async_retrieve_encryption_key",
        side_effect=SwitchbotAuthenticationError("error from api"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {"base": "auth_failed"}
    assert "error from api" in result["description_placeholders"]["error_detail"]

    with (
        patch_async_setup_entry() as mock_setup_entry,
        patch(
            "switchbot.SwitchbotRelaySwitch.async_retrieve_encryption_key",
            return_value={
                CONF_KEY_ID: "ff",
                CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
            },
        ),
        patch(
            "switchbot.SwitchbotRelaySwitch.verify_encryption_key", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Relay Switch 1PM EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "relay_switch_1pm",
    }

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_scanners_all_passive")
async def test_user_setup_worelay_switch_1pm_auth_switchbot_api_down(
    hass: HomeAssistant,
) -> None:
    """Test user form for relay switch 1pm when switchbot api is down."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
        return_value=[WORELAY_SWITCH_1PM_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "select_device"},
        )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"next_step_id": "encrypted_auth"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "encrypted_auth"
    assert result["errors"] == {}

    with patch(
        "switchbot.SwitchbotRelaySwitch.async_retrieve_encryption_key",
        side_effect=SwitchbotAccountConnectionError("Switchbot API down"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "api_error"
    assert result["description_placeholders"] == {"error_detail": "Switchbot API down"}


async def test_user_show_menu_when_passive_scanner_present(hass: HomeAssistant) -> None:
    """Test that menu is shown when any scanner is in passive mode."""
    mock_scanner_active = Mock()
    mock_scanner_active.current_mode = BluetoothScanningMode.ACTIVE
    mock_scanner_passive = Mock()
    mock_scanner_passive.current_mode = BluetoothScanningMode.PASSIVE

    with (
        patch(
            "homeassistant.components.bluetooth.async_current_scanners",
            return_value=[mock_scanner_active, mock_scanner_passive],
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOHAND_SERVICE_INFO],
        ),
        patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        # Should show menu since not all scanners are active
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"
        assert set(result["menu_options"]) == {
            "oauth_login",
            "cloud_login",
            "select_device",
        }

        # Choose select_device from menu
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "select_device"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirm the device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_show_menu_when_no_scanners(hass: HomeAssistant) -> None:
    """Test that menu is shown when no scanners are available."""
    with (
        patch(
            "homeassistant.components.bluetooth.async_current_scanners",
            return_value=[],
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOHAND_SERVICE_INFO],
        ),
        patch_async_setup_entry() as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        # Should show menu when no scanners are available
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"
        assert set(result["menu_options"]) == {
            "oauth_login",
            "cloud_login",
            "select_device",
        }

        # Choose select_device from menu
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "select_device"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirm the device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bot EEFF"
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "token",
    [
        pytest.param({}, id="missing-access-token"),
        pytest.param(
            {CONF_ACCESS_TOKEN: OAUTH_ACCESS_TOKEN}, id="missing-continuation"
        ),
    ],
)
async def test_oauth_create_entry_invalid_data(
    hass: HomeAssistant, token: dict[str, object]
) -> None:
    """Test invalid OAuth entry data aborts setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    handler = hass.config_entries.flow._progress[result["flow_id"]]

    result = await handler.async_oauth_create_entry({CONF_TOKEN: token})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host", "mock_scanners_all_passive")
async def test_user_oauth_login(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth authorization, token exchange, and normal device setup."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    authorize_url = URL(result["url"])

    assert str(authorize_url.with_query(None)) == f"{OAUTH_AUTHORIZE_URL}/"
    assert dict(authorize_url.query) == {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": config_entry_oauth2_flow.MY_AUTH_CALLBACK_PATH,
        "state": state,
        "scope": OAUTH_SCOPE,
    }
    assert "client_secret" not in authorize_url.query
    assert "code_challenge" not in authorize_url.query
    assert "code_challenge_method" not in authorize_url.query

    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200

    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": OAUTH_ACCESS_TOKEN,
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_expires_in": 2592000,
        },
    )
    with (
        patch(
            "homeassistant.components.switchbot.config_flow.fetch_cloud_devices_by_token"
        ) as mock_fetch_cloud_devices,
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOHAND_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    mock_fetch_cloud_devices.assert_awaited_once_with(ANY, OAUTH_ACCESS_TOKEN)
    assert aioclient_mock.mock_calls == [
        (
            "POST",
            URL(OAUTH_TOKEN_URL),
            {
                "grant_type": "authorization_code",
                "code": "authorization-code",
                "redirect_uri": config_entry_oauth2_flow.MY_AUTH_CALLBACK_PATH,
                "client_id": OAUTH_CLIENT_ID,
            },
            None,
        )
    ]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
        CONF_SENSOR_TYPE: "bot",
    }
    assert "token" not in result["data"]
    assert "auth_implementation" not in result["data"]


@pytest.mark.usefixtures("current_request_with_host")
async def test_encrypted_device_oauth_login(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth started directly from an encrypted Bluetooth discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOLOCK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"
    assert result["menu_options"][0] == "encrypted_oauth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "encrypted_oauth"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    state = _oauth_state(hass, result["flow_id"])

    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": OAUTH_ACCESS_TOKEN,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    key_details = {
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
    }
    with (
        patch_async_setup_entry(),
        patch(
            "switchbot.SwitchbotLock.async_retrieve_encryption_key_by_token",
            return_value=key_details,
        ) as mock_retrieve_key,
        patch("switchbot.SwitchbotLock.verify_encryption_key", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    mock_retrieve_key.assert_awaited_once_with(
        ANY, WOLOCK_SERVICE_INFO.address, OAUTH_ACCESS_TOKEN
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }
    assert "token" not in result["data"]


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("exception", "reason", "description_placeholders"),
    [
        pytest.param(
            SwitchbotAuthenticationError("invalid token"),
            "oauth_unauthorized",
            None,
            id="authentication",
        ),
        pytest.param(
            SwitchbotAccountConnectionError("API unavailable"),
            "api_error",
            {"error_detail": "API unavailable"},
            id="connection",
        ),
        pytest.param(
            SwitchbotApiError("API error"),
            "api_error",
            {"error_detail": "API error"},
            id="api",
        ),
        pytest.param(
            Exception("unexpected"),
            "unknown",
            None,
            id="unknown",
        ),
    ],
)
async def test_encrypted_device_oauth_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
    reason: str,
    description_placeholders: dict[str, str] | None,
) -> None:
    """Test errors retrieving an encrypted device key with an OAuth token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=WOLOCK_SERVICE_INFO,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "encrypted_oauth"}
    )
    state = _oauth_state(hass, result["flow_id"])

    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={"access_token": OAUTH_ACCESS_TOKEN, "expires_in": 3600},
    )

    with patch(
        "switchbot.SwitchbotLock.async_retrieve_encryption_key_by_token",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert result.get("description_placeholders") == description_placeholders


@pytest.mark.usefixtures("current_request_with_host", "mock_scanners_all_passive")
async def test_oauth_token_reused_for_encrypted_device(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a token from cloud discovery is reused to retrieve an encryption key."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": OAUTH_ACCESS_TOKEN,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    with (
        patch(
            "homeassistant.components.switchbot.config_flow.fetch_cloud_devices_by_token"
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[WOLOCK_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "encrypted_choose_method"

    key_details = {
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
    }
    with (
        patch_async_setup_entry(),
        patch(
            "switchbot.SwitchbotLock.async_retrieve_encryption_key_by_token",
            return_value=key_details,
        ) as mock_retrieve_key,
        patch("switchbot.SwitchbotLock.verify_encryption_key", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "encrypted_oauth"}
        )

    mock_retrieve_key.assert_awaited_once_with(
        ANY, WOLOCK_SERVICE_INFO.address, OAUTH_ACCESS_TOKEN
    )
    assert aioclient_mock.call_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
        CONF_KEY_ID: "ff",
        CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        CONF_SENSOR_TYPE: "lock",
    }


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_user_rejected_authorization(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test the user rejecting SwitchBot authorization."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?error=access_denied&state={state}"
    )
    assert response.status == 200

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "user_rejected_authorize"
    assert result["description_placeholders"] == {"error": "access_denied"}


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    "token_response",
    [
        pytest.param(
            {"access_token": OAUTH_ACCESS_TOKEN},
            id="missing-expires-in",
        ),
        pytest.param(
            {"expires_in": 3600},
            id="missing-access-token",
        ),
        pytest.param(
            {"access_token": OAUTH_ACCESS_TOKEN, "expires_in": "invalid"},
            id="invalid-expires-in",
        ),
    ],
)
async def test_oauth_invalid_token_response(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    token_response: dict[str, object],
) -> None:
    """Test invalid token responses abort setup."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(OAUTH_TOKEN_URL, json=token_response)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.usefixtures("current_request_with_host")
async def test_oauth_malformed_library_token_not_logged(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a malformed library response does not expose its access token."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200

    with patch(
        "homeassistant.components.switchbot.config_flow.exchange_oauth_code",
        return_value={"access_token": OAUTH_ACCESS_TOKEN},
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_error"
    assert OAUTH_ACCESS_TOKEN not in caplog.text


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("status", "error", "reason"),
    [
        pytest.param(400, "invalid_grant", "oauth_unauthorized", id="client-error"),
        pytest.param(429, "token_error", "oauth_failed", id="rate-limited"),
        pytest.param(500, "token_error", "oauth_failed", id="server-error"),
    ],
)
async def test_oauth_token_http_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: str,
    reason: str,
) -> None:
    """Test token endpoint HTTP errors abort setup."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        status=status,
        json={"error": error},
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            SwitchbotAuthenticationError("invalid token"),
            "oauth_unauthorized",
            id="authentication",
        ),
        pytest.param(
            SwitchbotAccountConnectionError("API unavailable"),
            "api_error",
            id="connection",
        ),
        pytest.param(
            SwitchbotApiError("API error"),
            "api_error",
            id="api",
        ),
        pytest.param(
            Exception("unexpected"),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_oauth_cloud_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
    reason: str,
) -> None:
    """Test cloud API errors after OAuth token exchange."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": OAUTH_ACCESS_TOKEN,
            "expires_in": 3600,
        },
    )
    with patch(
        "homeassistant.components.switchbot.config_flow.fetch_cloud_devices_by_token",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("current_request_with_host", "mock_scanners_all_passive")
async def test_oauth_no_devices(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test OAuth login when no Bluetooth devices are found."""
    result = await _async_start_user_oauth(hass)
    state = _oauth_state(hass, result["flow_id"])
    client = await hass_client_no_auth()
    response = await client.get(
        f"/auth/external/callback?code=authorization-code&state={state}"
    )
    assert response.status == 200
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": OAUTH_ACCESS_TOKEN,
            "expires_in": 3600,
        },
    )
    with (
        patch(
            "homeassistant.components.switchbot.config_flow.fetch_cloud_devices_by_token"
        ),
        patch(
            "homeassistant.components.switchbot.config_flow.async_discovered_service_info",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.parametrize("sensor_type", ["lock_pro_wifi", "lock_ultra_max"])
async def test_options_flow_lock_with_night_latch(
    hass: HomeAssistant, sensor_type: str
) -> None:
    """Test updating options for locks with night latch support."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: sensor_type,
        },
        options={CONF_RETRY_COUNT: 10},
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    # Test night_latch should be disabled by default.
    with patch_async_setup_entry() as mock_setup_entry:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_RETRY_COUNT: 3,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCK_NIGHTLATCH] is False

    assert len(mock_setup_entry.mock_calls) == 1

    # Test Set force night_latch to be enabled.
    with patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] is None

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCK_NIGHTLATCH: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCK_NIGHTLATCH] is True

    assert len(mock_setup_entry.mock_calls) == 0

    assert entry.options[CONF_LOCK_NIGHTLATCH] is True
