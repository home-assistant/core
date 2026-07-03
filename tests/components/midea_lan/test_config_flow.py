"""Tests for the Midea LAN config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from midealocal.const import ProtocolVersion
from midealocal.device import AuthException
from midealocal.exceptions import SocketException
import pytest

from homeassistant.components.midea_lan.config_flow import (
    DEFAULT_CLOUD,
    SKIP_LOGIN_OPTION,
    MideaLanConfigFlow,
)
from homeassistant.components.midea_lan.const import (
    CONF_ACCOUNT,
    CONF_KEY,
    CONF_SERVER,
    CONF_SUBTYPE,
    DOMAIN,
)
from homeassistant.components.midea_lan.device_catalog import MIDEA_DEVICE_NAMES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    BASE_DATA,
    DISCOVERY_RESULT,
    EXTENDED_DATA,
    TEST_DEVICE_ID,
    TEST_IP_ADDRESS,
    TEST_KEY,
    TEST_MODEL,
    TEST_NAME,
    TEST_PORT,
    TEST_PROTOCOL,
    TEST_SUBTYPE,
    TEST_TOKEN,
    TEST_TYPE,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def _start_user_flow(hass: HomeAssistant) -> MideaLanConfigFlow:
    """Start user flow and return its handler instance."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = next(iter(hass.config_entries.flow._progress))
    flow = hass.config_entries.flow._progress[flow_id]
    assert isinstance(flow, MideaLanConfigFlow)
    return flow


async def test_manual_flow_success(hass: HomeAssistant) -> None:
    """Test a successful manual configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_device.authenticate.return_value = None
        mock_midea_device.return_value = mock_device

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "manually"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manually"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={**EXTENDED_DATA},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MIDEA_DEVICE_NAMES[TEST_TYPE]
    assert result["data"] == {
        CONF_NAME: MIDEA_DEVICE_NAMES[TEST_TYPE],
        CONF_DEVICE_ID: TEST_DEVICE_ID,
        CONF_TYPE: TEST_TYPE,
        CONF_PROTOCOL: TEST_PROTOCOL,
        CONF_IP_ADDRESS: TEST_IP_ADDRESS,
        CONF_PORT: TEST_PORT,
        CONF_MODEL: TEST_MODEL,
        CONF_SUBTYPE: TEST_SUBTYPE,
        CONF_TOKEN: TEST_TOKEN,
        CONF_KEY: TEST_KEY,
    }


async def test_manual_flow_invalid_token(hass: HomeAssistant) -> None:
    """Test manual flow shows an error when token/key are not valid hex."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    invalid_input = {**EXTENDED_DATA}
    invalid_input[CONF_TOKEN] = "zz"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input=invalid_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "invalid_token"}


async def test_manual_flow_duplicate_unique_id(hass: HomeAssistant) -> None:
    """Test manual flow aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=str(TEST_DEVICE_ID),
        version=1,
        minor_version=1,
        data={CONF_DEVICE_ID: TEST_DEVICE_ID, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_device.authenticate.return_value = None
        mock_midea_device.return_value = mock_device

        await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "manually"},
        )
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={**EXTENDED_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_search_filters_already_configured_device(hass: HomeAssistant) -> None:
    """Test search excludes already configured devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_ID: TEST_DEVICE_ID, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: TEST_IP_ADDRESS},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "no_devices"}


async def test_auto_flow_uses_cloud_name_for_entry_title(hass: HomeAssistant) -> None:
    """Test cloud-reported device name is used for entry title and CONF_NAME."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={
            TEST_DEVICE_ID: {
                **BASE_DATA,
                CONF_TYPE: TEST_TYPE,
                CONF_PROTOCOL: ProtocolVersion.V2,
            }
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": TEST_SUBTYPE}
    )

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        dm = MagicMock()
        dm.connect.return_value = True
        mock_midea_device.return_value = dm

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "pass",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auto"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_DEVICE: TEST_DEVICE_ID},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manually"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                **EXTENDED_DATA,
                CONF_PROTOCOL: ProtocolVersion.V2,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"][CONF_NAME] == TEST_NAME


async def test_manual_step_invalid_device_id_after_auto(hass: HomeAssistant) -> None:
    """Test manual step returns form error when edited device_id is unknown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "search"},
    )

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={
            TEST_DEVICE_ID: {
                **BASE_DATA,
                CONF_TYPE: TEST_TYPE,
                CONF_PROTOCOL: ProtocolVersion.V2,
            }
        },
    ):
        await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: "auto"},
        )

    await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(return_value={"name": TEST_NAME})

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: "skip_login_option",
                CONF_ACCOUNT: "account",
                CONF_PASSWORD: "password",
            },
        )

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={
            **EXTENDED_DATA,
            CONF_DEVICE_ID: TEST_DEVICE_ID + 1,
            CONF_PROTOCOL: ProtocolVersion.V2,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "invalid_device_id"}


@pytest.mark.parametrize(
    "cloud_servers",
    [
        pytest.param({}, id="empty_servers"),
        pytest.param({1: "CN", 2: DEFAULT_CLOUD}, id="has_servers"),
    ],
)
async def test_login_form_renders_with_cloud_servers(
    hass: HomeAssistant,
    cloud_servers: dict[int, str],
) -> None:
    """Test login step renders form regardless of cloud server list shape."""
    flow = await _start_user_flow(hass)
    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
        AsyncMock(return_value=cloud_servers),
    ):
        result = await flow.async_step_login()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"


@pytest.mark.parametrize(
    ("server", "expected_mode"),
    [
        pytest.param(SKIP_LOGIN_OPTION, "preset", id="skip_login"),
        pytest.param(DEFAULT_CLOUD, "input", id="explicit_login"),
    ],
)
async def test_login_step_login_failed_sets_error(
    hass: HomeAssistant,
    server: str,
    expected_mode: str,
) -> None:
    """Test login failures stay on login step with proper error state."""
    flow = await _start_user_flow(hass)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: DEFAULT_CLOUD}),
        ),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=False)),
    ):
        result = await flow.async_step_login(
            {
                CONF_SERVER: server,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "pass",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert result["errors"] == {"base": "login_failed"}
    assert flow._login_mode == expected_mode


@pytest.mark.parametrize(
    ("all_devices", "expected_table_fragment"),
    [
        pytest.param({}, "Not found", id="empty"),
        pytest.param(
            {
                TEST_DEVICE_ID: {
                    CONF_TYPE: TEST_TYPE,
                    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                    "sn": "abc",
                }
            },
            "YES",
            id="single_device",
        ),
    ],
)
async def test_list_step_shows_discovery_table(
    hass: HomeAssistant,
    all_devices: dict[int, dict[str, object]],
    expected_table_fragment: str,
) -> None:
    """Test list step shows either table output or not-found message."""
    flow = await _start_user_flow(hass)
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=all_devices,
    ):
        result = await flow.async_step_list()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "list"
    assert expected_table_fragment in result["description_placeholders"]["table"]


async def test_list_step_submit_returns_to_user_menu(hass: HomeAssistant) -> None:
    """Test submitting list step returns user menu."""
    flow = await _start_user_flow(hass)
    result = await flow.async_step_list(user_input={"ok": True})

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


@pytest.mark.parametrize(
    ("login_ok", "expected"),
    [
        pytest.param(True, True, id="cloud_login_ok"),
        pytest.param(False, False, id="cloud_login_fail"),
    ],
)
async def test_check_cloud_login_uses_defaults_when_args_missing(
    hass: HomeAssistant,
    login_ok: bool,
    expected: bool,
) -> None:
    """Test cloud login helper defaults to preset credentials when args are missing."""
    flow = await _start_user_flow(hass)
    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=login_ok)
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await flow._check_cloud_login()

    assert result is expected


async def test_check_key_from_cloud_success(hass: HomeAssistant) -> None:
    """Test cloud key retrieval returns token/key on successful authentication."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_SUBTYPE: TEST_SUBTYPE,
        }
    }

    flow.cloud = MagicMock()
    flow.cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )
    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.return_value = None

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={"default": "value"}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await flow._check_key_from_cloud(TEST_DEVICE_ID, default_key=True)

    assert result == {"token": TEST_TOKEN, "key": TEST_KEY}


@pytest.mark.parametrize(
    ("default_key", "keys", "connect", "authenticate_side_effect"),
    [
        pytest.param(
            False,
            {"default": {"token": TEST_TOKEN, "key": TEST_KEY}},
            True,
            None,
            id="skip_default_key",
        ),
        pytest.param(
            True,
            {"method": {"token": TEST_TOKEN, "key": TEST_KEY}},
            False,
            None,
            id="connect_fails",
        ),
        pytest.param(
            True,
            {"method": {"token": TEST_TOKEN, "key": TEST_KEY}},
            True,
            AuthException,
            id="auth_exception",
        ),
        pytest.param(
            True,
            {"method": {"token": TEST_TOKEN, "key": TEST_KEY}},
            True,
            SocketException,
            id="socket_exception",
        ),
    ],
)
async def test_check_key_from_cloud_connect_error_paths(
    hass: HomeAssistant,
    default_key: bool,
    keys: dict[str, dict[str, str]],
    connect: bool,
    authenticate_side_effect: type[Exception] | None,
) -> None:
    """Test cloud key retrieval returns connect_error in failure paths."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_SUBTYPE: TEST_SUBTYPE,
        }
    }
    flow.cloud = MagicMock()
    flow.cloud.get_cloud_keys = AsyncMock(return_value=keys)
    dm = MagicMock()
    dm.connect.return_value = connect
    dm.authenticate.return_value = None
    dm.authenticate.side_effect = authenticate_side_effect

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={"default": "value"}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await flow._check_key_from_cloud(
            TEST_DEVICE_ID, default_key=default_key
        )

    assert result == {"error": "connect_error"}


async def test_check_key_from_cloud_cloud_none(hass: HomeAssistant) -> None:
    """Test key retrieval returns cloud_none when cloud object was not initialised."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_SUBTYPE: TEST_SUBTYPE,
        }
    }
    result = await flow._check_key_from_cloud(TEST_DEVICE_ID)
    assert result == {"error": "cloud_none"}


async def test_auto_step_rejects_unknown_selected_device(hass: HomeAssistant) -> None:
    """Test auto step returns no_devices when selected device id is unknown."""
    flow = await _start_user_flow(hass)
    flow.devices = {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}}
    flow.available_device = {TEST_DEVICE_ID: "device"}

    result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID + 1})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"
    assert result["errors"] == {"base": "no_devices"}


async def test_auto_step_with_no_available_device_shows_error(
    hass: HomeAssistant,
) -> None:
    """Test auto step currently recurses when no available devices exist."""
    flow = await _start_user_flow(hass)
    flow.available_device = {}

    with pytest.raises(RecursionError):
        await flow.async_step_auto()


@pytest.mark.parametrize(
    (
        "login_mode",
        "cloud_login_phase2",
        "keys_phase1",
        "keys_phase2",
        "expected_error",
    ),
    [
        pytest.param(
            "preset",
            True,
            {"error": "connect_error"},
            {"error": "connect_error"},
            "token_unavailable",
            id="preset_mode_token_unavailable",
        ),
        pytest.param(
            "input",
            False,
            {"error": "connect_error"},
            {"error": "connect_error"},
            "preset_login_failed",
            id="phase2_login_fail",
        ),
        pytest.param(
            "input",
            True,
            {"error": "connect_error"},
            {"error": "connect_error"},
            "token_unavailable",
            id="phase2_token_still_unavailable",
        ),
    ],
)
async def test_auto_step_v3_token_retrieval_fallbacks(
    hass: HomeAssistant,
    login_mode: str,
    cloud_login_phase2: bool,
    keys_phase1: dict[str, str],
    keys_phase2: dict[str, str],
    expected_error: str,
) -> None:
    """Test V3 token acquisition fallback behavior in auto step."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_PROTOCOL: ProtocolVersion.V3,
        }
    }
    flow._login_mode = login_mode
    flow._login_data = {
        CONF_SERVER: DEFAULT_CLOUD,
        CONF_ACCOUNT: "acc",
        CONF_PASSWORD: "pwd",
    }
    flow.available_device = {TEST_DEVICE_ID: "device"}
    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(return_value=None)
    flow.cloud = cloud

    with (
        patch.object(
            flow,
            "_check_key_from_cloud",
            AsyncMock(side_effect=[keys_phase1, keys_phase2]),
        ),
        patch.object(
            flow,
            "_check_cloud_login",
            AsyncMock(return_value=cloud_login_phase2),
        ),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"
    assert result["errors"] == {"base": expected_error}


async def test_auto_step_cached_login_failure_clears_login_state(
    hass: HomeAssistant,
) -> None:
    """Test cached-login failure clears flow login state and returns login step."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_PROTOCOL: ProtocolVersion.V2,
        }
    }
    flow._login_mode = "input"
    flow._login_data = {
        CONF_SERVER: DEFAULT_CLOUD,
        CONF_ACCOUNT: "acc",
        CONF_PASSWORD: "pwd",
    }
    flow.cloud = None

    with (
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=False)),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: DEFAULT_CLOUD}),
        ),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert flow._login_data is None
    assert flow._login_mode is None
    assert flow.cloud is None


@pytest.mark.parametrize(
    ("discovery_result", "input_id", "expected_error"),
    [
        pytest.param({}, TEST_DEVICE_ID, "invalid_device_ip", id="discover_empty"),
        pytest.param(
            {
                TEST_DEVICE_ID + 1: {
                    **BASE_DATA,
                    CONF_TYPE: TEST_TYPE,
                    CONF_PROTOCOL: TEST_PROTOCOL,
                    CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                }
            },
            TEST_DEVICE_ID,
            "invalid_device_id_for_ip",
            id="discover_id_mismatch",
        ),
    ],
)
async def test_manual_step_discovery_validation_errors(
    hass: HomeAssistant,
    discovery_result: dict[int, dict[str, object]],
    input_id: int,
    expected_error: str,
) -> None:
    """Test manual step discovery validation for missing/mismatched devices."""
    flow = await _start_user_flow(hass)
    flow.devices = {}
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=discovery_result,
    ):
        result = await flow.async_step_manually(
            {
                **EXTENDED_DATA,
                CONF_DEVICE_ID: input_id,
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("device", "user_input", "expected_error"),
    [
        pytest.param(
            {
                **BASE_DATA,
                CONF_TYPE: TEST_TYPE,
                CONF_PROTOCOL: TEST_PROTOCOL,
                CONF_IP_ADDRESS: "2.2.2.2",
            },
            {**EXTENDED_DATA},
            "ip_address_mismatch",
            id="ip_mismatch",
        ),
        pytest.param(
            {
                **BASE_DATA,
                CONF_TYPE: TEST_TYPE,
                CONF_PROTOCOL: ProtocolVersion.V2,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            },
            {**EXTENDED_DATA, CONF_PROTOCOL: ProtocolVersion.V3},
            "protocol_mismatch",
            id="protocol_mismatch",
        ),
        pytest.param(
            {
                **BASE_DATA,
                CONF_TYPE: TEST_TYPE,
                CONF_PROTOCOL: TEST_PROTOCOL,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            },
            {**EXTENDED_DATA},
            "device_auth_failed",
            id="connect_fails",
        ),
    ],
)
async def test_manual_step_runtime_validation_and_auth_errors(
    hass: HomeAssistant,
    device: dict[str, object],
    user_input: dict[str, object],
    expected_error: str,
) -> None:
    """Test manual step mismatch and connect-failure branches."""
    flow = await _start_user_flow(hass)
    flow.devices = {TEST_DEVICE_ID: device}

    dm = MagicMock()
    dm.connect.return_value = False
    dm.authenticate.return_value = None

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaDevice", return_value=dm
    ):
        result = await flow.async_step_manually(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("authenticate_side_effect", "expected_error"),
    [
        pytest.param(SocketException, "device_auth_failed", id="socket_error"),
        pytest.param(AuthException, "device_auth_failed", id="auth_error"),
    ],
)
async def test_manual_step_authenticate_exceptions(
    hass: HomeAssistant,
    authenticate_side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test manual step handles authenticate exceptions as auth failure."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_PROTOCOL: ProtocolVersion.V3,
            CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            CONF_SUBTYPE: TEST_SUBTYPE,
        }
    }
    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = authenticate_side_effect

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaDevice", return_value=dm
    ):
        result = await flow.async_step_manually(
            {**EXTENDED_DATA, CONF_PROTOCOL: ProtocolVersion.V3}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("cloud_login_ok", "keys", "expected_error"),
    [
        pytest.param(
            False,
            {"token": TEST_TOKEN, "key": TEST_KEY},
            "preset_login_failed",
            id="preset_login_fails",
        ),
        pytest.param(
            True,
            {"error": "connect_error"},
            "token_unavailable",
            id="no_token_from_cloud",
        ),
    ],
)
async def test_manual_step_v3_missing_token_key_uses_cloud(
    hass: HomeAssistant,
    cloud_login_ok: bool,
    keys: dict[str, str],
    expected_error: str,
) -> None:
    """Test V3 manual path retrieves missing token/key or returns expected errors."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_PROTOCOL: ProtocolVersion.V3,
            CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            CONF_SUBTYPE: TEST_SUBTYPE,
        }
    }

    with (
        patch.object(
            flow, "_check_cloud_login", AsyncMock(return_value=cloud_login_ok)
        ),
        patch.object(flow, "_check_key_from_cloud", AsyncMock(return_value=keys)),
    ):
        result = await flow.async_step_manually(
            {
                **EXTENDED_DATA,
                CONF_PROTOCOL: ProtocolVersion.V3,
                CONF_TOKEN: "",
                CONF_KEY: "",
            }
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": expected_error}


async def test_auto_step_v3_token_success_sets_found_device_and_clears_login(
    hass: HomeAssistant,
) -> None:
    """Test auto step stores retrieved V3 token/key and clears login state."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_PROTOCOL: ProtocolVersion.V3,
        }
    }
    flow._login_mode = "input"
    flow._login_data = {
        CONF_SERVER: DEFAULT_CLOUD,
        CONF_ACCOUNT: "acc",
        CONF_PASSWORD: "pwd",
    }
    flow.available_device = {TEST_DEVICE_ID: "device"}
    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(return_value=None)
    flow.cloud = cloud

    with (
        patch.object(
            flow,
            "_check_key_from_cloud",
            AsyncMock(return_value={"token": TEST_TOKEN, "key": TEST_KEY}),
        ),
        patch.object(
            flow,
            "async_step_manually",
            AsyncMock(
                return_value={"type": FlowResultType.FORM, "step_id": "manually"}
            ),
        ) as mock_manual,
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert flow.found_device[CONF_TOKEN] == TEST_TOKEN
    assert flow.found_device[CONF_KEY] == TEST_KEY
    assert flow._login_data is None
    assert flow._login_mode is None
    assert flow.cloud is None
    assert mock_manual.await_count == 1


async def test_manual_step_v3_missing_token_key_sets_retrieved_values(
    hass: HomeAssistant,
) -> None:
    """Test manual step writes cloud-provided token/key into user_input."""
    flow = await _start_user_flow(hass)
    flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_TYPE: TEST_TYPE,
            CONF_PROTOCOL: ProtocolVersion.V3,
            CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            CONF_SUBTYPE: TEST_SUBTYPE,
        }
    }
    user_input: dict[str, object] = {
        **EXTENDED_DATA,
        CONF_PROTOCOL: ProtocolVersion.V3,
        CONF_TOKEN: "",
        CONF_KEY: "",
    }
    dm = MagicMock()
    dm.connect.return_value = False
    dm.authenticate.return_value = None

    with (
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=True)),
        patch.object(
            flow,
            "_check_key_from_cloud",
            AsyncMock(return_value={"token": TEST_TOKEN, "key": TEST_KEY}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await flow.async_step_manually(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "device_auth_failed"}
    assert user_input[CONF_TOKEN] == TEST_TOKEN
    assert user_input[CONF_KEY] == TEST_KEY
