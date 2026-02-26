"""Tests for the Midea LAN config flow."""

from collections.abc import Generator
from pathlib import Path
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

from midealocal.const import ProtocolVersion
from midealocal.device import AuthException
from midealocal.exceptions import SocketException
import pytest

from homeassistant.components.midea_lan.config_flow import (
    DEFAULT_CLOUD,
    MideaLanConfigFlow,
    MideaLanOptionsFlowHandler,
)
from homeassistant.components.midea_lan.const import (
    CONF_ACCOUNT,
    CONF_KEY,
    CONF_MODEL,
    CONF_REFRESH_INTERVAL,
    CONF_SERVER,
    CONF_SUBTYPE,
    DOMAIN,
)
from homeassistant.components.midea_lan.devices import MIDEA_DEVICES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_CUSTOMIZE,
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_TOKEN,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_DEVICE_ID = 12345678
TEST_IP_ADDRESS = "192.0.2.10"
TEST_PORT = 6444
TEST_PROTOCOL = ProtocolVersion.V3
TEST_TYPE = next(iter(MIDEA_DEVICES))
TEST_MODEL = "MSAGBU-09HRFN8"
TEST_SUBTYPE = 0
TEST_NAME = "Bedroom AC"
TEST_TOKEN = "aa" * 16
TEST_KEY = "bb" * 16


@pytest.fixture
def flow(hass: HomeAssistant) -> MideaLanConfigFlow:
    """Return a configured config flow instance."""
    config_flow = MideaLanConfigFlow()
    config_flow.hass = hass
    return config_flow


@pytest.fixture
def mock_device_config_storage(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict]:
    """Mock config-flow storage I/O in memory without creating files."""
    storage: dict[str, dict] = {}

    def fake_save_json(path: str, data: dict) -> None:
        storage[path] = data.copy()

    def fake_load_json(path: str, default: dict | None = None) -> dict:
        if path in storage:
            return storage[path]
        return default if default is not None else {}

    def fake_exists(self: Path) -> bool:
        return str(self) in storage

    class _FakeFile:
        def __init__(self, name: str) -> None:
            """Initialize fake file object."""
            self.name = name

        def __enter__(self) -> Self:
            """Enter context manager."""
            return self

        def __exit__(self, *_args: object) -> bool:
            """Exit context manager."""
            return False

    def fake_open(self: Path, encoding: str | None = None) -> _FakeFile:
        return _FakeFile(str(self))

    monkeypatch.setattr(
        "homeassistant.components.midea_lan.config_flow.save_json",
        fake_save_json,
    )
    monkeypatch.setattr(
        "homeassistant.components.midea_lan.config_flow.load_json",
        fake_load_json,
    )
    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "open", fake_open)
    return storage


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent loading the integration during config flow tests."""
    with patch(
        "homeassistant.components.midea_lan.async_setup_entry",
        return_value=True,
    ) as mock_entry:
        yield mock_entry


def _discovery_result() -> dict[int, dict]:
    """Return a single discovered device for manual flow validation."""
    return {
        TEST_DEVICE_ID: {
            CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            CONF_PORT: TEST_PORT,
            CONF_PROTOCOL: TEST_PROTOCOL,
            CONF_TYPE: TEST_TYPE,
            CONF_MODEL: TEST_MODEL,
        }
    }


def _manual_user_input() -> dict:
    """Return user input for the manual step."""
    return {
        CONF_NAME: TEST_NAME,
        CONF_DEVICE_ID: TEST_DEVICE_ID,
        CONF_TYPE: TEST_TYPE,
        CONF_IP_ADDRESS: TEST_IP_ADDRESS,
        CONF_PORT: TEST_PORT,
        CONF_PROTOCOL: TEST_PROTOCOL,
        CONF_MODEL: TEST_MODEL,
        CONF_SUBTYPE: TEST_SUBTYPE,
        CONF_TOKEN: TEST_TOKEN,
        CONF_KEY: TEST_KEY,
    }


async def test_manual_flow_success(hass: HomeAssistant) -> None:
    """Test a successful manual configuration flow."""
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=_discovery_result(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaLanConfigFlow._save_device_config",
        ),
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_device.authenticate.return_value = None
        mock_midea_device.return_value = mock_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"action": "manually"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manually"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=_manual_user_input(),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_NAME: TEST_NAME,
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"action": "manually"},
    )

    invalid_input = _manual_user_input()
    invalid_input[CONF_TOKEN] = "zz"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "invalid_token"}


async def test_manual_flow_duplicate_unique_id(hass: HomeAssistant) -> None:
    """Test manual flow aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_ID,
        version=2,
        minor_version=1,
        data={CONF_DEVICE_ID: TEST_DEVICE_ID, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=_discovery_result(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
        ) as mock_midea_device,
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaLanConfigFlow._save_device_config",
        ),
    ):
        mock_device = MagicMock()
        mock_device.connect.return_value = True
        mock_device.authenticate.return_value = None
        mock_midea_device.return_value = mock_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"action": "manually"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=_manual_user_input(),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def test_storage_helpers(
    flow: MideaLanConfigFlow,
    mock_device_config_storage: dict[str, dict],
) -> None:
    """Test saving and loading device config from storage."""
    data = {
        CONF_DEVICE_ID: TEST_DEVICE_ID,
        CONF_NAME: TEST_NAME,
        CONF_TYPE: TEST_TYPE,
    }

    flow._save_device_config(data)

    loaded = flow._load_device_config(str(TEST_DEVICE_ID))
    assert loaded[CONF_DEVICE_ID] == TEST_DEVICE_ID
    assert loaded[CONF_NAME] == TEST_NAME
    assert len(mock_device_config_storage) == 1

    assert flow._load_device_config("does_not_exist") == {}


def test_check_storage_device() -> None:
    """Test storage-device validation helper."""
    assert not MideaLanConfigFlow._check_storage_device(
        {CONF_PROTOCOL: ProtocolVersion.V3},
        {},
    )
    assert not MideaLanConfigFlow._check_storage_device(
        {CONF_PROTOCOL: ProtocolVersion.V3},
        {CONF_SUBTYPE: 1, CONF_TOKEN: None, CONF_KEY: None},
    )
    assert MideaLanConfigFlow._check_storage_device(
        {CONF_PROTOCOL: ProtocolVersion.V3},
        {CONF_SUBTYPE: 1, CONF_TOKEN: TEST_TOKEN, CONF_KEY: TEST_KEY},
    )


async def test_step_user_routes(flow: MideaLanConfigFlow) -> None:
    """Test step_user routes actions to the expected next steps."""
    with (
        patch.object(flow, "async_step_discovery", AsyncMock(return_value={"step": 1})),
        patch.object(flow, "async_step_manually", AsyncMock(return_value={"step": 2})),
        patch.object(flow, "async_step_cache", AsyncMock(return_value={"step": 3})),
        patch.object(flow, "async_step_list", AsyncMock(return_value={"step": 4})),
    ):
        assert await flow.async_step_user({"action": "discovery"}) == {"step": 1}
        flow.found_device = {"x": 1}
        assert await flow.async_step_user({"action": "manually"}) == {"step": 2}
        assert flow.found_device == {}
        assert await flow.async_step_user({"action": "cache"}) == {"step": 3}
        assert await flow.async_step_user({"action": "list"}) == {"step": 4}

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_cache(flow: MideaLanConfigFlow) -> None:
    """Test cache step clears login cache and displays form."""
    flow.hass.data[DOMAIN] = {
        "login_data": {CONF_ACCOUNT: "a", CONF_SERVER: "s", CONF_PASSWORD: "p"},
        "login_mode": "input",
    }
    with patch.object(flow, "async_step_user", AsyncMock(return_value={"done": True})):
        result = await flow.async_step_cache({"action": "remove"})
    assert result == {"done": True}
    assert flow.hass.data[DOMAIN] == {}

    result = await flow.async_step_cache()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "cache"


async def test_step_list(flow: MideaLanConfigFlow) -> None:
    """Test list step for discovered and empty-device results."""
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={
            TEST_DEVICE_ID: {
                CONF_TYPE: TEST_TYPE,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
                "sn": "123",
            }
        },
    ):
        result = await flow.async_step_list()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "list"
    assert "Appliance code" in result["description_placeholders"]["table"]

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover", return_value={}
    ):
        result = await flow.async_step_list()
    assert result["description_placeholders"]["table"] == "Not found"


async def test_step_discovery(flow: MideaLanConfigFlow) -> None:
    """Test discovery step form and auto route."""
    result = await flow.async_step_discovery()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery"

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=_discovery_result(),
        ),
        patch.object(
            flow, "async_step_auto", AsyncMock(return_value={"ok": True})
        ) as mock_auto,
    ):
        result = await flow.async_step_discovery({CONF_IP_ADDRESS: "auto"})
    assert result == {"ok": True}
    assert mock_auto.called

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=_discovery_result(),
        ),
        patch.object(flow, "async_step_auto", AsyncMock(return_value={"ok": "ip"})),
    ):
        result = await flow.async_step_discovery({CONF_IP_ADDRESS: TEST_IP_ADDRESS})
    assert result == {"ok": "ip"}

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={},
    ):
        result = await flow.async_step_discovery({CONF_IP_ADDRESS: TEST_IP_ADDRESS})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_check_cloud_login(flow: MideaLanConfigFlow) -> None:
    """Test cloud login helper for success and failure."""
    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        assert await flow._check_cloud_login("s", "a", "p", True)

    cloud.login = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
        return_value=cloud,
    ):
        assert not await flow._check_cloud_login("s", "a", "p", True)

    cloud.login = AsyncMock(return_value=True)
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        assert await flow._check_cloud_login()


async def test_check_key_from_cloud(flow: MideaLanConfigFlow) -> None:
    """Test key/token retrieval helper."""
    flow.devices = _discovery_result()
    flow.cloud = MagicMock()
    flow.cloud.get_cloud_keys = AsyncMock(
        return_value={1: {"token": TEST_TOKEN, "key": TEST_KEY}}
    )

    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.return_value = None

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={1: {"token": "x", "key": "y"}}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await flow._check_key_from_cloud(TEST_DEVICE_ID)

    assert result == {"token": TEST_TOKEN, "key": TEST_KEY}


async def test_check_key_from_cloud_edge_cases(flow: MideaLanConfigFlow) -> None:
    """Test key helper branches for cloud missing and all-key failures."""
    flow.devices = _discovery_result()
    flow.cloud = None
    result = await flow._check_key_from_cloud(TEST_DEVICE_ID)
    assert result == {"error": "cloud_none"}

    flow.cloud = MagicMock()
    flow.cloud.get_cloud_keys = AsyncMock(
        return_value={
            1: {"token": TEST_TOKEN, "key": TEST_KEY},
            2: {"token": TEST_TOKEN, "key": TEST_KEY},
        }
    )
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={1: {"token": "x", "key": "y"}}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=MagicMock(connect=MagicMock(return_value=False)),
        ),
    ):
        result = await flow._check_key_from_cloud(TEST_DEVICE_ID, default_key=False)
    assert result == {"error": "connect_error"}


async def test_check_key_from_cloud_auth_and_socket_exceptions(
    flow: MideaLanConfigFlow,
) -> None:
    """Test key helper handles device auth and socket exceptions."""
    flow.devices = _discovery_result()
    flow.cloud = MagicMock()
    flow.cloud.get_cloud_keys = AsyncMock(
        return_value={
            1: {"token": "t1", "key": "k1"},
            2: {"token": "t2", "key": "k2"},
        }
    )

    auth_dm = MagicMock()
    auth_dm.connect.return_value = True
    auth_dm.authenticate.side_effect = AuthException("nope")

    socket_dm = MagicMock()
    socket_dm.connect.return_value = True
    socket_dm.authenticate.side_effect = SocketException("closed")

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={9: {"token": "x", "key": "y"}}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            side_effect=[auth_dm, socket_dm],
        ),
    ):
        result = await flow._check_key_from_cloud(TEST_DEVICE_ID)
    assert result == {"error": "connect_error"}


async def test_step_login_branches(flow: MideaLanConfigFlow) -> None:
    """Test login step form, skip-login, input-login, and failure branches."""
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={99: {"token": "x", "key": "y"}}),
        ),
    ):
        result = await flow.async_step_login()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={99: {"token": "x", "key": "y"}}),
        ),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=True)),
        patch.object(flow, "async_step_auto", AsyncMock(return_value={"auto": True})),
    ):
        result = await flow.async_step_login(
            {CONF_SERVER: 99, CONF_ACCOUNT: "a", CONF_PASSWORD: "p"}
        )
    assert result == {"auto": True}
    assert flow.hass.data[DOMAIN]["login_mode"] == "preset"

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={99: {"token": "x", "key": "y"}}),
        ),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=False)),
    ):
        result = await flow.async_step_login(
            {CONF_SERVER: 1, CONF_ACCOUNT: "user", CONF_PASSWORD: "pw"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "login_failed"}


async def test_step_auto_cached_login_failure(flow: MideaLanConfigFlow) -> None:
    """Test auto step clears invalid cached login and routes to login step."""
    flow.devices = _discovery_result()
    flow.available_device = {TEST_DEVICE_ID: "Device"}
    flow.hass.data[DOMAIN] = {
        "login_mode": "input",
        "login_data": {CONF_SERVER: "CN", CONF_ACCOUNT: "u", CONF_PASSWORD: "p"},
    }
    flow.cloud = None

    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=False)),
        patch.object(flow, "async_step_login", AsyncMock(return_value={"login": True})),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result == {"login": True}
    assert flow.hass.data[DOMAIN] == {}


async def test_step_auto_v3_key_retrieval_paths(flow: MideaLanConfigFlow) -> None:
    """Test auto step V3 key retrieval fallback and success branches."""
    flow.devices = _discovery_result()
    flow.available_device = {TEST_DEVICE_ID: "Device"}
    flow.hass.data[DOMAIN] = {
        "login_mode": "preset",
        "login_data": {CONF_SERVER: "CN", CONF_ACCOUNT: "u", CONF_PASSWORD: "p"},
    }
    flow.cloud = MagicMock()
    flow.cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )

    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(flow, "_check_key_from_cloud", AsyncMock(return_value={})),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"

    flow.hass.data[DOMAIN]["login_mode"] = "input"
    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(flow, "_check_key_from_cloud", AsyncMock(side_effect=[{}, {}])),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=False)),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result["type"] is FlowResultType.FORM

    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(flow, "_check_key_from_cloud", AsyncMock(side_effect=[{}, {}])),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=True)),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result["type"] is FlowResultType.FORM

    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(
            flow,
            "_check_key_from_cloud",
            AsyncMock(return_value={"token": TEST_TOKEN, "key": TEST_KEY}),
        ),
        patch.object(
            flow, "async_step_manually", AsyncMock(return_value={"manual": True})
        ),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result == {"manual": True}


async def test_step_auto_non_v3_goes_manual(flow: MideaLanConfigFlow) -> None:
    """Test auto step routes non-V3 devices directly to manual step."""
    flow.devices = {
        TEST_DEVICE_ID: {
            **_discovery_result()[TEST_DEVICE_ID],
            CONF_PROTOCOL: ProtocolVersion.V2,
        }
    }
    flow.available_device = {TEST_DEVICE_ID: "Device"}
    flow.hass.data[DOMAIN] = {
        "login_mode": "input",
        "login_data": {CONF_SERVER: "CN", CONF_ACCOUNT: "u", CONF_PASSWORD: "p"},
    }
    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=True)),
        patch.object(
            flow, "async_step_manually", AsyncMock(return_value={"manual": True})
        ),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result == {"manual": True}


async def test_step_auto_routes(flow: MideaLanConfigFlow) -> None:
    """Test auto step routes to manually or login depending on state."""
    flow.devices = _discovery_result()
    flow.available_device = {TEST_DEVICE_ID: "Device"}

    with (
        patch.object(
            flow,
            "_load_device_config",
            return_value={
                CONF_NAME: TEST_NAME,
                CONF_SUBTYPE: TEST_SUBTYPE,
                CONF_TOKEN: TEST_TOKEN,
                CONF_KEY: TEST_KEY,
            },
        ),
        patch.object(
            flow, "async_step_manually", AsyncMock(return_value={"manual": True})
        ),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result == {"manual": True}

    with (
        patch.object(flow, "_load_device_config", return_value={}),
        patch.object(flow, "async_step_login", AsyncMock(return_value={"login": True})),
    ):
        result = await flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result == {"login": True}


async def test_manual_step_validations(flow: MideaLanConfigFlow) -> None:
    """Test manual step validation branches."""
    user_input = _manual_user_input()

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover", return_value={}
    ):
        result = await flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_device_ip"}

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={TEST_DEVICE_ID + 1: _discovery_result()[TEST_DEVICE_ID]},
    ):
        result = await flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM

    flow.devices = {
        TEST_DEVICE_ID: {
            **_discovery_result()[TEST_DEVICE_ID],
            CONF_IP_ADDRESS: "10.0.0.1",
        }
    }
    result = await flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM

    flow.devices = {
        TEST_DEVICE_ID: {
            **_discovery_result()[TEST_DEVICE_ID],
            CONF_PROTOCOL: ProtocolVersion.V2,
        }
    }
    result = await flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM


async def test_manual_step_token_fetch_paths(flow: MideaLanConfigFlow) -> None:
    """Test manual step token/key fetch branches for empty credentials."""
    user_input = _manual_user_input()
    user_input[CONF_TOKEN] = ""
    user_input[CONF_KEY] = ""
    flow.devices = _discovery_result()

    with patch.object(flow, "_check_cloud_login", AsyncMock(return_value=False)):
        result = await flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM

    with (
        patch.object(flow, "_check_cloud_login", AsyncMock(return_value=True)),
        patch.object(flow, "_check_key_from_cloud", AsyncMock(return_value={})),
    ):
        result = await flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM

    dm = MagicMock()
    dm.connect.return_value = False
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


async def test_manual_step_auth_failure(flow: MideaLanConfigFlow) -> None:
    """Test manual step handles authentication failure."""
    flow.devices = _discovery_result()
    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = AuthException("bad")

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaDevice", return_value=dm
    ):
        result = await flow.async_step_manually(_manual_user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "Device auth failed with input config"}


async def test_manual_step_socket_exception(flow: MideaLanConfigFlow) -> None:
    """Test manual step handles socket exception during authentication."""
    flow.devices = _discovery_result()
    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = SocketException("closed")

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaDevice", return_value=dm
    ):
        result = await flow.async_step_manually(_manual_user_input())

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "Device auth failed with input config"}


async def test_options_flow(flow: MideaLanConfigFlow) -> None:
    """Test options flow abort/create/form branches."""
    account_entry = MockConfigEntry(domain=DOMAIN, data={CONF_TYPE: CONF_ACCOUNT})
    account_options = MideaLanOptionsFlowHandler(account_entry)
    result = await account_options.async_step_init()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_option"

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TYPE: TEST_TYPE, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
        options={
            CONF_REFRESH_INTERVAL: 30,
            CONF_SENSORS: [],
            CONF_SWITCHES: [],
            CONF_CUSTOMIZE: "",
        },
    )
    options_flow = MideaLanOptionsFlowHandler(entry)

    create_result = await options_flow.async_step_init(
        {CONF_IP_ADDRESS: TEST_IP_ADDRESS}
    )
    assert create_result["type"] is FlowResultType.CREATE_ENTRY

    form_result = await options_flow.async_step_init()
    assert form_result["type"] is FlowResultType.FORM
    assert form_result["step_id"] == "init"


def test_async_get_options_flow() -> None:
    """Test async_get_options_flow returns expected handler."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TYPE: TEST_TYPE})
    options_flow = MideaLanConfigFlow.async_get_options_flow(entry)
    assert isinstance(options_flow, MideaLanOptionsFlowHandler)


async def test_options_flow_filters_and_schema_branches() -> None:
    """Test options init filtering and schema extension branches."""
    fake_devices = {
        TEST_TYPE: {
            "entities": {
                "sensor_attr": {"type": "sensor", "name": "Sensor attr"},
                "switch_attr": {
                    "type": "switch",
                    "name": "Switch attr",
                    "default": False,
                },
            }
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TYPE: TEST_TYPE},
        options={
            CONF_SENSORS: ["sensor_attr", "invalid_sensor"],
            CONF_SWITCHES: ["switch_attr", "invalid_switch"],
        },
    )

    with patch(
        "homeassistant.components.midea_lan.config_flow.MIDEA_DEVICES",
        fake_devices,
    ):
        options_flow = MideaLanOptionsFlowHandler(entry)
        assert "invalid_sensor" not in options_flow._config_entry.options[CONF_SENSORS]
        assert "invalid_switch" not in options_flow._config_entry.options[CONF_SWITCHES]

        form_result = await options_flow.async_step_init()
    assert form_result["type"] is FlowResultType.FORM


def test_options_flow_type_defaults_to_0xac() -> None:
    """Test options flow defaults type when missing from entry data."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    options_flow = MideaLanOptionsFlowHandler(entry)
    assert options_flow._device_type == 0xAC


def test_already_configured_helper(flow: MideaLanConfigFlow) -> None:
    """Test _already_configured helper true/false branches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_ID: str(TEST_DEVICE_ID), CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    flow._async_current_entries = MagicMock(return_value=[entry])

    assert flow._already_configured(str(TEST_DEVICE_ID), "198.51.100.1")
    assert flow._already_configured("999", TEST_IP_ADDRESS)
    assert not flow._already_configured("999", "198.51.100.2")
