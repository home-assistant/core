"""Tests for the Midea LAN config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from midealocal.const import ProtocolVersion
from midealocal.device import AuthException
from midealocal.exceptions import SocketException
import pytest

from homeassistant.components.midea_lan.config_flow import (
    DEFAULT_CLOUD,
    LOGIN_MODE_ACCOUNT,
    LOGIN_MODE_PRESET,
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
    TEST_PORT,
    TEST_PROTOCOL,
    TEST_SUBTYPE,
    TEST_TOKEN,
    TEST_TYPE,
)

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


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


@pytest.mark.parametrize(
    (
        "user_input",
        "discover_result",
        "connect_return",
        "authenticate_side_effect",
        "check_cloud_login_return",
        "check_key_from_cloud_return",
        "pre_input",
        "expected_error",
    ),
    [
        pytest.param(
            {**EXTENDED_DATA, CONF_TOKEN: "zz"},
            None,
            None,
            None,
            None,
            {},
            None,
            "invalid_token",
            id="invalid_token",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {},
            None,
            None,
            None,
            {},
            None,
            "invalid_device_ip",
            id="discover_empty",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {TEST_DEVICE_ID + 1: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            None,
            None,
            {},
            None,
            "invalid_device_id_for_ip",
            id="discover_id_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {
                TEST_DEVICE_ID: {
                    **BASE_DATA,
                    CONF_TYPE: TEST_TYPE,
                    CONF_IP_ADDRESS: "2.2.2.2",
                },
            },
            None,
            None,
            None,
            {},
            None,
            "ip_address_mismatch",
            id="ip_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {
                TEST_DEVICE_ID: {
                    **BASE_DATA,
                    CONF_TYPE: TEST_TYPE,
                    CONF_PROTOCOL: ProtocolVersion.V2,
                },
            },
            None,
            None,
            None,
            {},
            None,
            "protocol_mismatch",
            id="protocol_mismatch",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            False,
            None,
            None,
            {},
            None,
            "device_auth_failed",
            id="connect_fails",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            True,
            SocketException,
            None,
            {},
            None,
            "device_auth_failed",
            id="socket_error",
        ),
        pytest.param(
            {**EXTENDED_DATA},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            True,
            AuthException,
            None,
            {},
            None,
            "device_auth_failed",
            id="auth_error",
        ),
        pytest.param(
            {**EXTENDED_DATA, CONF_TOKEN: "", CONF_KEY: ""},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            None,
            False,
            {},
            None,
            "preset_login_failed",
            id="preset_login_fails",
        ),
        pytest.param(
            {**EXTENDED_DATA, CONF_TOKEN: "", CONF_KEY: ""},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            None,
            True,
            {"error": "connect_error"},
            None,
            "token_unavailable",
            id="no_token_from_cloud",
        ),
        pytest.param(
            {**EXTENDED_DATA, CONF_DEVICE_ID: TEST_DEVICE_ID + 1},
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            None,
            None,
            None,
            {},
            {**EXTENDED_DATA, CONF_IP_ADDRESS: "9.9.9.9"},
            "invalid_device_id",
            id="invalid_device_id",
        ),
    ],
)
async def test_manual_step_errors(
    hass: HomeAssistant,
    user_input: dict[str, object],
    discover_result: dict[int, dict[str, object]] | None,
    connect_return: bool | None,
    authenticate_side_effect: type[Exception] | None,
    check_cloud_login_return: bool | None,
    check_key_from_cloud_return: dict[str, str],
    pre_input: dict[str, object] | None,
    expected_error: str,
) -> None:
    """Test every async_step_manually error branch via one parametrized flow."""
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

    dm = MagicMock()
    dm.connect.return_value = connect_return
    dm.authenticate.side_effect = authenticate_side_effect

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=discover_result,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
        patch.object(
            MideaLanConfigFlow,
            "_check_cloud_login",
            AsyncMock(return_value=check_cloud_login_return),
        ),
        patch.object(
            MideaLanConfigFlow,
            "_check_key_from_cloud",
            AsyncMock(return_value=check_key_from_cloud_return),
        ),
    ):
        if pre_input is not None:
            await hass.config_entries.flow.async_configure(
                flow_id,
                user_input=pre_input,
            )
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("mock_devices", "cloud_data", "expected_type", "expected_error"),
    [
        pytest.param(
            DISCOVERY_RESULT,
            {"pre_existing_entry": True, "search_ip": TEST_IP_ADDRESS},
            FlowResultType.FORM,
            "no_devices",
            id="no_devices",
        ),
        pytest.param(
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            {"login": False},
            FlowResultType.FORM,
            "preset_login_failed",
            id="cached_credentials_fail",
        ),
        pytest.param(
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            {
                "login": True,
                "device_info": {"name": "Cloud Device Name", "model_number": "XYZ123"},
                "cloud_keys": {"method": {"token": TEST_TOKEN, "key": TEST_KEY}},
            },
            FlowResultType.CREATE_ENTRY,
            None,
            id="cloud_device_info_override",
        ),
        pytest.param(
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            {
                "login": True,
                "cloud_keys": {"method": {"token": TEST_TOKEN, "key": TEST_KEY}},
            },
            FlowResultType.CREATE_ENTRY,
            None,
            id="v3_cloud_keys_phase1_success",
        ),
        pytest.param(
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            {
                "login": True,
                "cloud_keys": [
                    {
                        "keyA": {"token": TEST_TOKEN, "key": TEST_KEY},
                        "keyB": {"token": TEST_TOKEN, "key": TEST_KEY},
                    },
                    {
                        "default": {"token": TEST_TOKEN, "key": TEST_KEY},
                        "keyC": {"token": TEST_TOKEN, "key": TEST_KEY},
                    },
                ],
                "default_keys": {"default": "value"},
                "connect": [True, True, False],
                "authenticate": [AuthException, SocketException],
            },
            FlowResultType.FORM,
            "token_unavailable",
            id="v3_token_retrieval_exhausted",
        ),
        pytest.param(
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            {"login": [True, False], "cloud_keys": {}},
            FlowResultType.FORM,
            "preset_login_failed",
            id="v3_phase2_login_failed",
        ),
        pytest.param(
            {TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
            {"login": [True, True], "cloud_keys": {}},
            FlowResultType.FORM,
            "token_unavailable",
            id="v3_phase2_no_keys",
        ),
    ],
)
async def test_search_and_auto_flow(
    hass: HomeAssistant,
    mock_devices: dict[int, dict[str, object]],
    cloud_data: dict[str, object],
    expected_type: FlowResultType,
    expected_error: str | None,
) -> None:
    """Test the search-and-auto discovery flow across success and failure modes."""
    if cloud_data.get("pre_existing_entry"):
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
        return_value=mock_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_IP_ADDRESS: cloud_data.get("search_ip", "auto")},
        )

    if result["step_id"] == "search":
        assert result["type"] is expected_type
        assert result["errors"] == {"base": expected_error}
        return

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    login_value = cloud_data.get("login", True)
    cloud = MagicMock()
    cloud.login = (
        AsyncMock(side_effect=login_value)
        if isinstance(login_value, list)
        else AsyncMock(return_value=login_value)
    )
    cloud.get_device_info = AsyncMock(return_value=cloud_data.get("device_info"))
    cloud_keys_value = cloud_data.get("cloud_keys", {})
    cloud.get_cloud_keys = (
        AsyncMock(side_effect=cloud_keys_value)
        if isinstance(cloud_keys_value, list)
        else AsyncMock(return_value=cloud_keys_value)
    )

    dm = MagicMock()
    connect_value = cloud_data.get("connect", True)
    if isinstance(connect_value, list):
        dm.connect.side_effect = connect_value
    else:
        dm.connect.return_value = connect_value
    dm.authenticate.side_effect = cloud_data.get("authenticate")

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value=cloud_data.get("default_keys", {})),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is expected_type
    if expected_error is not None:
        assert result["errors"] == {"base": expected_error}
    else:
        assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID


@pytest.mark.parametrize(
    "protocol",
    [
        pytest.param(ProtocolVersion.V1, id="v1"),
        pytest.param(ProtocolVersion.V2, id="v2"),
    ],
)
async def test_auto_flow_v1_v2_success_when_cloud_down(
    hass: HomeAssistant,
    protocol: ProtocolVersion,
) -> None:
    """Test v1/v2 devices are added without ever using the cloud, even if it is down."""
    mock_devices = {
        TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE, CONF_PROTOCOL: protocol},
    }

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

    dm = MagicMock()
    dm.connect.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
        patch.object(
            MideaLanConfigFlow,
            "_check_cloud_login",
            AsyncMock(side_effect=AssertionError("cloud must not be used")),
        ),
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_PROTOCOL] == protocol


async def test_login_credentials_step_renders_with_cloud_servers(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials step renders form regardless of cloud server list shape."""
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
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
        AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_ACCOUNT},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"


async def test_login_credentials_step_login_failed_sets_error(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials failures stay on the step with proper error state."""
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
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: DEFAULT_CLOUD}),
        ),
        patch.object(
            MideaLanConfigFlow, "_check_cloud_login", AsyncMock(return_value=False)
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "pass",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"
    assert result["errors"] == {"base": "login_failed"}


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
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=all_devices,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "list"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "list"
    assert expected_table_fragment in result["description_placeholders"]["table"]


async def test_list_step_submit_returns_to_user_menu(hass: HomeAssistant) -> None:
    """Test submitting list step returns user menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"next_step_id": "list"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "list"

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"ok": True},
        )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_manual_step_v3_missing_token_key_sets_retrieved_values(
    hass: HomeAssistant,
) -> None:
    """Test manual step writes cloud-provided token/key into user_input."""
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

    device = {
        **BASE_DATA,
        CONF_TYPE: TEST_TYPE,
        CONF_PROTOCOL: ProtocolVersion.V3,
        CONF_IP_ADDRESS: TEST_IP_ADDRESS,
        CONF_SUBTYPE: TEST_SUBTYPE,
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
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value={TEST_DEVICE_ID: device},
        ),
        patch.object(
            MideaLanConfigFlow, "_check_cloud_login", AsyncMock(return_value=True)
        ),
        patch.object(
            MideaLanConfigFlow,
            "_check_key_from_cloud",
            AsyncMock(return_value={"token": TEST_TOKEN, "key": TEST_KEY}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
    ):
        mock_midea_device.return_value = dm
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "device_auth_failed"}

    assert mock_midea_device.call_args.kwargs["token"] == TEST_TOKEN
    assert mock_midea_device.call_args.kwargs["key"] == TEST_KEY


async def test_manually_flow_success(hass: HomeAssistant) -> None:
    """Test the full manual configuration flow through to entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"next_step_id": "manually"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

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
            user_input={
                CONF_DEVICE_ID: TEST_DEVICE_ID,
                CONF_TYPE: TEST_TYPE,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                CONF_PORT: TEST_PORT,
                CONF_PROTOCOL: TEST_PROTOCOL,
                CONF_MODEL: TEST_MODEL,
                CONF_SUBTYPE: TEST_SUBTYPE,
                CONF_TOKEN: TEST_TOKEN,
                CONF_KEY: TEST_KEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MIDEA_DEVICE_NAMES[TEST_TYPE]
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert result["data"][CONF_IP_ADDRESS] == TEST_IP_ADDRESS
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY


async def test_login_credentials_step_falls_back_to_default_cloud(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials step falls back to DEFAULT_CLOUD with no cloud servers."""
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
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
        AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_ACCOUNT},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"


async def test_login_credentials_step_success_resumes_auto_flow(
    hass: HomeAssistant,
) -> None:
    """Test login_credentials step stores login data and resumes device processing."""
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

    discovered_device = {
        TEST_DEVICE_ID: {**BASE_DATA, CONF_TYPE: TEST_TYPE},
    }
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=discovered_device,
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
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(return_value=None)
    cloud.get_cloud_keys = AsyncMock(
        return_value={"method": {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.return_value = True

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_get_clientsession",
            return_value=object(),
        ) as mock_session,
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ) as mock_get_midea_cloud,
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_SERVER: DEFAULT_CLOUD,
                CONF_ACCOUNT: "user",
                CONF_PASSWORD: "pass",
            },
        )

    mock_get_midea_cloud.assert_called_once_with(
        DEFAULT_CLOUD, mock_session.return_value, "user", "pass"
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_ID


async def test_auth_method_account_mode_redirects_to_login_credentials(
    hass: HomeAssistant,
) -> None:
    """Test auth_method step routes to login_credentials when account mode is chosen."""
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
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={"login_mode": LOGIN_MODE_ACCOUNT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login_credentials"


async def test_auth_method_preset_login_failed(hass: HomeAssistant) -> None:
    """Test auth_method step surfaces preset_login_failed when preset login fails."""
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
            user_input={CONF_IP_ADDRESS: "auto"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_DEVICE: TEST_DEVICE_ID},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=False)

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
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={"login_mode": LOGIN_MODE_PRESET},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth_method"
    assert result["errors"] == {"base": "preset_login_failed"}
