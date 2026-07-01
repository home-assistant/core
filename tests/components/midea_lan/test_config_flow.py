"""Tests for the Midea LAN config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from midealocal.const import ProtocolVersion
from midealocal.device import AuthException
from midealocal.exceptions import SocketException
import pytest

from homeassistant.components.midea_lan.config_flow import (
    DEFAULT_CLOUD,
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_flow_success(hass: HomeAssistant) -> None:
    """Test a successful manual configuration flow."""
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

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": "manually"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manually"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_flow_invalid_token(hass: HomeAssistant) -> None:
    """Test manual flow shows an error when token/key are not valid hex."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "manually"},
    )

    invalid_input = {**EXTENDED_DATA}
    invalid_input[CONF_TOKEN] = "zz"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"
    assert result["errors"] == {"base": "invalid_token"}


@pytest.mark.usefixtures("mock_setup_entry")
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

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"next_step_id": "manually"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**EXTENDED_DATA},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_user_routes(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test step_user exposes menu options."""
    result = await mock_config_flow.async_step_user()
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["search", "manually", "list"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_list(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test list step for discovered, empty-device, and user submission."""

    # Case 1: device found
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={
            TEST_DEVICE_ID: {
                CONF_TYPE: TEST_TYPE,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            }
        },
    ):
        result = await mock_config_flow.async_step_list()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "list"
    assert "Appliance code" in result["description_placeholders"]["table"]

    # Case 2: no devices found
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover", return_value={}
    ):
        result = await mock_config_flow.async_step_list()

    assert result["description_placeholders"]["table"] == "Not found"

    # Case 3: form submitted
    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={
            TEST_DEVICE_ID: {
                CONF_TYPE: TEST_TYPE,
                CONF_IP_ADDRESS: TEST_IP_ADDRESS,
            }
        },
    ):
        result = await mock_config_flow.async_step_list(
            user_input={TEST_DEVICE_ID: True}
        )

    assert result["type"] == FlowResultType.MENU


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_search(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test search step form and auto route."""
    result = await mock_config_flow.async_step_search()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch.object(
            mock_config_flow, "async_step_auto", AsyncMock(return_value={"ok": True})
        ) as mock_auto,
    ):
        result = await mock_config_flow.async_step_search({CONF_IP_ADDRESS: "auto"})
    assert result == {"ok": True}
    assert mock_auto.called

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.discover",
            return_value=DISCOVERY_RESULT,
        ),
        patch.object(
            mock_config_flow, "async_step_auto", AsyncMock(return_value={"ok": "ip"})
        ),
    ):
        result = await mock_config_flow.async_step_search(
            {CONF_IP_ADDRESS: TEST_IP_ADDRESS}
        )
    assert result == {"ok": "ip"}

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={},
    ):
        result = await mock_config_flow.async_step_search(
            {CONF_IP_ADDRESS: TEST_IP_ADDRESS}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_search_filters_already_configured_device(
    hass: HomeAssistant,
) -> None:
    """Test search filters devices that are already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE_ID: TEST_DEVICE_ID, CONF_IP_ADDRESS: TEST_IP_ADDRESS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value=DISCOVERY_RESULT,
    ):
        result = await flow.async_step_search({CONF_IP_ADDRESS: TEST_IP_ADDRESS})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    assert result["errors"] == {"base": "no_devices"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_login_branches(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test login step form, skip-login, input-login, and failure branches."""
    mock_config_flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_PROTOCOL: ProtocolVersion.V2,
            CONF_TYPE: TEST_TYPE,
        }
    }
    mock_config_flow.available_device = {TEST_DEVICE_ID: "Device"}

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
    ):
        result = await mock_config_flow.async_step_login()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"

    cloud = MagicMock()
    cloud.login = AsyncMock(return_value=True)
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {
                CONF_SERVER: "skip_login_option",
                CONF_ACCOUNT: "account",
                CONF_PASSWORD: "password",
            }
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auto"

        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    mock_config_flow.cloud = None

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
    ):
        cloud = MagicMock()
        cloud.login = AsyncMock(return_value=False)
        with patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ):
            result = await mock_config_flow.async_step_login(
                {CONF_SERVER: 1, CONF_ACCOUNT: "user", CONF_PASSWORD: "pw"}
            )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "login_failed"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_auto_cached_login_failure(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test auto step clears invalid cached login and routes to login step."""
    mock_config_flow.devices = DISCOVERY_RESULT
    mock_config_flow.available_device = {TEST_DEVICE_ID: "Device"}

    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )

    login_calls = 0

    async def _login() -> bool:
        nonlocal login_calls
        login_calls += 1
        if login_calls == 1:
            mock_config_flow.cloud = None
            return True
        return False

    cloud.login = AsyncMock(side_effect=_login)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {CONF_SERVER: 1, CONF_ACCOUNT: "account", CONF_PASSWORD: "password"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auto"

        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_auto_v3_key_retrieval_paths(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test auto step V3 key retrieval fallback and success branches."""
    mock_config_flow.devices = DISCOVERY_RESULT
    mock_config_flow.available_device = {TEST_DEVICE_ID: "Device"}

    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )
    cloud.get_cloud_keys = AsyncMock(
        return_value={1: {"token": TEST_TOKEN, "key": TEST_KEY}}
    )
    cloud.login = AsyncMock(return_value=True)

    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.return_value = None

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {
                CONF_SERVER: "skip_login_option",
                CONF_ACCOUNT: "account",
                CONF_PASSWORD: "password",
            }
        )
        assert result["step_id"] == "auto"
        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "manually"
        result = await mock_config_flow.async_step_manually({**EXTENDED_DATA})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_KEY] == TEST_KEY

    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )
    cloud.get_cloud_keys = AsyncMock(return_value={})
    cloud.login = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {
                CONF_SERVER: "skip_login_option",
                CONF_ACCOUNT: "account",
                CONF_PASSWORD: "password",
            }
        )
        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}

    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )
    cloud.get_cloud_keys = AsyncMock(
        side_effect=[
            {},
            {
                1: {"token": "cc" * 16, "key": "dd" * 16},
                2: {"token": TEST_TOKEN, "key": TEST_KEY},
            },
        ]
    )
    cloud.login = AsyncMock(side_effect=[True, True])

    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.return_value = None

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_default_keys",
            AsyncMock(return_value={1: {"token": "cc" * 16, "key": "dd" * 16}}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {CONF_SERVER: 1, CONF_ACCOUNT: "user", CONF_PASSWORD: "pw"}
        )
        assert result["step_id"] == "auto"
        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"

    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )
    cloud.get_cloud_keys = AsyncMock(return_value={})
    cloud.login = AsyncMock(side_effect=[True, False])

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {CONF_SERVER: 1, CONF_ACCOUNT: "user", CONF_PASSWORD: "pw"}
        )
        assert result["step_id"] == "auto"
        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "preset_login_failed"}

    cloud = MagicMock()
    cloud.get_device_info = AsyncMock(
        return_value={"name": TEST_NAME, "model_number": 7}
    )
    cloud.get_cloud_keys = AsyncMock(return_value={})
    cloud.login = AsyncMock(side_effect=[True, True])

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await mock_config_flow.async_step_login(
            {CONF_SERVER: 1, CONF_ACCOUNT: "user", CONF_PASSWORD: "pw"}
        )
        assert result["step_id"] == "auto"
        result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_auto_non_v3_goes_manual(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test auto step routes non-V3 devices directly to manual step."""
    mock_config_flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_PROTOCOL: ProtocolVersion.V2,
            CONF_TYPE: TEST_TYPE,
        }
    }
    mock_config_flow.available_device = {TEST_DEVICE_ID: "Device"}
    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
    ):
        cloud = MagicMock()
        cloud.get_device_info = AsyncMock(
            return_value={"name": TEST_NAME, "model_number": 7}
        )
        cloud.login = AsyncMock(return_value=True)
        with patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ):
            result = await mock_config_flow.async_step_login(
                {
                    CONF_SERVER: "skip_login_option",
                    CONF_ACCOUNT: "account",
                    CONF_PASSWORD: "password",
                }
            )
            assert result["step_id"] == "auto"
            result = await mock_config_flow.async_step_auto(
                {CONF_DEVICE: TEST_DEVICE_ID}
            )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manually"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_auto_routes(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test auto step routes to login when auth data is missing."""
    mock_config_flow.devices = DISCOVERY_RESULT
    mock_config_flow.available_device = {TEST_DEVICE_ID: "Device"}

    result = await mock_config_flow.async_step_auto({CONF_DEVICE: TEST_DEVICE_ID})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_auto_device_not_in_devices(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test auto step error when selected device is not in devices."""
    mock_config_flow.available_device = {TEST_DEVICE_ID: "Device"}
    mock_config_flow.devices = {}

    result = await mock_config_flow.async_step_auto(
        {CONF_DEVICE: TEST_DEVICE_ID},
        error=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auto"
    assert result["errors"] == {"base": "no_devices"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_step_validations(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test manual step validation branches."""
    user_input = {**EXTENDED_DATA}

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover", return_value={}
    ):
        result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_device_ip"}

    with patch(
        "homeassistant.components.midea_lan.config_flow.discover",
        return_value={TEST_DEVICE_ID + 1: {**BASE_DATA, CONF_TYPE: TEST_TYPE}},
    ):
        result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM

    mock_config_flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_IP_ADDRESS: "10.0.0.1",
            CONF_TYPE: TEST_TYPE,
        }
    }
    result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM

    mock_config_flow.devices = {
        TEST_DEVICE_ID: {
            **BASE_DATA,
            CONF_PROTOCOL: ProtocolVersion.V2,
            CONF_TYPE: TEST_TYPE,
        }
    }
    result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_step_token_fetch_paths(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test manual step token/key fetch branches for empty credentials."""
    user_input = {**EXTENDED_DATA}
    user_input[CONF_TOKEN] = ""
    user_input[CONF_KEY] = ""
    mock_config_flow.devices = DISCOVERY_RESULT

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
    ):
        cloud = MagicMock()
        cloud.login = AsyncMock(return_value=False)
        with patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ):
            result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "preset_login_failed"}

    dm = MagicMock()
    dm.connect.return_value = False

    mock_config_flow.cloud = None

    cloud = MagicMock()
    cloud.login = AsyncMock(
        side_effect=lambda: setattr(mock_config_flow, "cloud", None) or True
    )

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}

    mock_config_flow.cloud = None

    dm = MagicMock()
    dm.connect.return_value = False
    cloud = MagicMock()
    cloud.get_cloud_keys = AsyncMock(
        return_value={1: {"token": TEST_TOKEN, "key": TEST_KEY}}
    )
    cloud.login = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}

    mock_config_flow.cloud = None

    cloud = MagicMock()
    cloud.get_cloud_keys = AsyncMock(return_value={})
    cloud.login = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
    ):
        result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}

    mock_config_flow.cloud = None

    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = AuthException("bad")
    cloud = MagicMock()
    cloud.get_cloud_keys = AsyncMock(
        return_value={1: {"token": TEST_TOKEN, "key": TEST_KEY}}
    )
    cloud.login = AsyncMock(return_value=True)

    with (
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaCloud.get_cloud_servers",
            AsyncMock(return_value={1: "CN", 2: DEFAULT_CLOUD}),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.async_create_clientsession",
            return_value=object(),
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.get_midea_cloud",
            return_value=cloud,
        ),
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await mock_config_flow.async_step_manually(user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_step_token_fetch_handles_socket_exception(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test manual step handles socket exception while validating cloud keys."""
    user_input = {**EXTENDED_DATA}
    user_input[CONF_TOKEN] = ""
    user_input[CONF_KEY] = ""
    mock_config_flow.devices = DISCOVERY_RESULT

    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = SocketException("closed")

    cloud = MagicMock()
    cloud.get_cloud_keys = AsyncMock(
        return_value={1: {"token": TEST_TOKEN, "key": TEST_KEY}}
    )
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
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            return_value=dm,
        ),
    ):
        result = await mock_config_flow.async_step_manually(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "token_unavailable"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_step_token_fetch_sets_preset_keys(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test manual step copies preset token/key before device validation."""
    user_input = {**EXTENDED_DATA}
    user_input[CONF_TOKEN] = ""
    user_input[CONF_KEY] = ""
    mock_config_flow.devices = DISCOVERY_RESULT

    helper_dm = MagicMock()
    helper_dm.connect.return_value = True
    helper_dm.authenticate.return_value = None

    manual_dm = MagicMock()
    manual_dm.connect.return_value = False

    cloud = MagicMock()
    cloud.get_cloud_keys = AsyncMock(
        return_value={1: {"token": TEST_TOKEN, "key": TEST_KEY}}
    )
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
        patch(
            "homeassistant.components.midea_lan.config_flow.MideaDevice",
            side_effect=[helper_dm, manual_dm],
        ),
    ):
        result = await mock_config_flow.async_step_manually(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_auth_failed"}
    assert user_input[CONF_TOKEN] == TEST_TOKEN
    assert user_input[CONF_KEY] == TEST_KEY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_step_auth_failure(mock_config_flow: MideaLanConfigFlow) -> None:
    """Test manual step handles authentication failure."""
    mock_config_flow.devices = DISCOVERY_RESULT
    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = AuthException("bad")

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaDevice", return_value=dm
    ):
        result = await mock_config_flow.async_step_manually({**EXTENDED_DATA})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_auth_failed"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_step_socket_exception(
    mock_config_flow: MideaLanConfigFlow,
) -> None:
    """Test manual step handles socket exception during authentication."""
    mock_config_flow.devices = DISCOVERY_RESULT
    dm = MagicMock()
    dm.connect.return_value = True
    dm.authenticate.side_effect = SocketException("closed")

    with patch(
        "homeassistant.components.midea_lan.config_flow.MideaDevice", return_value=dm
    ):
        result = await mock_config_flow.async_step_manually({**EXTENDED_DATA})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_auth_failed"}
