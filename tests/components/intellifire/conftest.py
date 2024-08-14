"""Fixtures for IntelliFire integration tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

from aiohttp.client_reqrep import ConnectionKey
from intellifire4py.const import IntelliFireApiMode
from intellifire4py.exceptions import LoginError
from intellifire4py.model import (
    IntelliFireCommonFireplaceData,
    IntelliFirePollData,
    IntelliFireUserData,
)
import pytest

from homeassistant.components.intellifire.const import (
    API_MODE_CLOUD,
    API_MODE_LOCAL,
    CONF_AUTH_COOKIE,
    CONF_CONTROL_MODE,
    CONF_READ_MODE,
    CONF_SERIAL,
    CONF_USER_ID,
    CONF_WEB_CLIENT_ID,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.intellifire.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_cloud_api_interface_user_data_1() -> IntelliFireUserData:
    """Fixture to mock the user_data property of IntelliFireCloudInterface."""
    fixture_data = load_fixture("intellifire/user_data_1.json")
    user_data_mock = IntelliFireUserData(**json.loads(fixture_data))
    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireCloudInterface.user_data",
        new_callable=PropertyMock,
    ) as mock_user_data:
        mock_user_data.return_value = user_data_mock
        yield


@pytest.fixture
def mock_cloud_api_interface_user_data_3() -> IntelliFireUserData:
    """Fixture to mock the user_data property of IntelliFireCloudInterface."""
    fixture_data = load_fixture("intellifire/user_data_3.json")
    user_data_mock = IntelliFireUserData(**json.loads(fixture_data))

    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireCloudInterface.user_data",
        new_callable=PropertyMock,
    ) as mock_user_data:
        mock_user_data.return_value = user_data_mock
        yield


@pytest.fixture
def mock_local_poll_data() -> IntelliFirePollData:
    """Mock polling a local fireplace."""
    fixture_data = load_fixture("intellifire/local_poll.json")
    poll_data_mock = IntelliFirePollData(**json.loads(fixture_data))

    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireAPILocal.data",
        new_callable=PropertyMock,
    ) as mock_user_data:
        mock_user_data.return_value = poll_data_mock
        yield


@pytest.fixture
def mock_login_with_credentials() -> Generator[AsyncMock, None, None]:
    """Mock the login_with_credentials method and set _user_data."""

    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireCloudInterface.login_with_credentials",
        new_callable=AsyncMock,
    ) as mock_login:
        # mock_login.side_effect = login_side_effect
        yield mock_login


@pytest.fixture
def mock_login_with_bad_credentials() -> Generator[AsyncMock, None, None]:
    """Mock the login_with_credentials method and set _user_data."""

    # Custom side effect function
    async def side_effect_func(*args, **kwargs):
        if not hasattr(side_effect_func, "called"):
            side_effect_func.called = True
            raise LoginError
        # Simulate async function

    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireCloudInterface.login_with_credentials",
        new_callable=AsyncMock,
    ) as mock_login:
        mock_login.side_effect = side_effect_func
        yield mock_login


@pytest.fixture
def mock_poll_local_fireplace() -> Generator[AsyncMock, None, None]:
    """Mock polling of local fireplace."""
    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireAPILocal.poll",
        new_callable=AsyncMock,
    ) as mock_poll:
        # mock_login.side_effect = login_side_effect
        yield mock_poll


@pytest.fixture
def mock_cloud_poll() -> Generator[AsyncMock, None, None]:
    """Mock a successful cloud poll call."""
    with patch(
        "homeassistant.components.intellifire.__init__.UnifiedFireplace.perform_cloud_poll",
        new_callable=AsyncMock,
    ) as mock_poll:
        # mock_login.side_effect = login_side_effect
        yield mock_poll


@pytest.fixture
def mock_connectivity_test_pass_pass() -> Generator[AsyncMock, None, None]:
    """Mock both Cloud and Local Connectivity."""
    with patch(
        "homeassistant.components.intellifire.__init__.UnifiedFireplace.async_validate_connectivity",
        new_callable=AsyncMock,
    ) as mock_connectivity:
        mock_connectivity.return_value = (True, True)
        yield mock_connectivity


@pytest.fixture
def mock_connectivity_test_fail_fail() -> Generator[AsyncMock, None, None]:
    """Mock both Cloud and Local Connectivity."""
    with patch(
        "homeassistant.components.intellifire.__init__.UnifiedFireplace.async_validate_connectivity",
        new_callable=AsyncMock,
    ) as mock_connectivity:
        mock_connectivity.return_value = (False, False)
        yield mock_connectivity


@pytest.fixture
def mock_connectivity_test_fail_fail_then_pass_pass() -> (
    Generator[AsyncMock, None, None]
):
    """Mock both Cloud and Local Connectivity."""
    return_values = [(False, False), (True, True), (True, True), (True, True)]

    with patch(
        "homeassistant.components.intellifire.__init__.UnifiedFireplace.async_validate_connectivity",
        new_callable=AsyncMock,
    ) as mock_connectivity:
        mock_connectivity.side_effect = return_values
        yield mock_connectivity


@pytest.fixture
def mock_poll_local_fireplace_exception() -> Generator[AsyncMock, None, None]:
    """Mock polling a fireplace that isn't a fireplace."""
    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireAPILocal.poll",
        new_callable=AsyncMock,
    ) as mock_poll:
        mock_poll.side_effect = ConnectionError
        yield mock_poll


@pytest.fixture
def mock_fireplace_finder_none() -> Generator[None, MagicMock, None]:
    """Mock fireplace finder."""
    mock_found_fireplaces = Mock()
    mock_found_fireplaces.ips = []
    with patch(
        "homeassistant.components.intellifire.config_flow.UDPFireplaceFinder.search_fireplace"
    ):
        yield mock_found_fireplaces


@pytest.fixture
def mock_config_entry_current() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_IP_ADDRESS: "192.168.2.108",
            CONF_USERNAME: "grumpypanda@china.cn",
            CONF_PASSWORD: "you-stole-my-pandas",
            CONF_SERIAL: "3FB284769E4736F30C8973A7ED358123",
            CONF_WEB_CLIENT_ID: "FA2B1C3045601234D0AE17D72F8E975",
            CONF_API_KEY: "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
            CONF_AUTH_COOKIE: "B984F21A6378560019F8A1CDE41B6782",
            CONF_USER_ID: "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        },
        options={CONF_READ_MODE: API_MODE_LOCAL, CONF_CONTROL_MODE: API_MODE_CLOUD},
        unique_id="serial",
    )


@pytest.fixture
def mock_config_entry_old() -> MockConfigEntry:
    """For migration testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Fireplace 3FB284769E4736F30C8973A7ED358123",
        data={
            CONF_HOST: "192.168.2.108",
            CONF_USERNAME: "grumpypanda@china.cn",
            CONF_PASSWORD: "you-stole-my-pandas",
            CONF_USER_ID: "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        },
    )


@pytest.fixture
def mock_config_entry_super_old() -> MockConfigEntry:
    """For migration testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Fireplace 3FB284769E4736F30C8973A7ED358123",
        data={CONF_HOST: "192.168.2.108"},
    )


@pytest.fixture
def mock_config_entry_v1_bad_title() -> MockConfigEntry:
    """For migration testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Fireplace Of Doom",
        data={
            CONF_HOST: "192.168.2.108",
            CONF_USERNAME: "grumpypanda@china.cn",
            CONF_PASSWORD: "you-stole-my-pandas",
            CONF_USER_ID: "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        },
    )


@pytest.fixture
def mock_fireplace_finder_single() -> Generator[None, MagicMock, None]:
    """Mock fireplace finder."""
    mock_found_fireplaces = Mock()
    mock_found_fireplaces.ips = ["192.168.1.69"]
    with patch(
        "homeassistant.components.intellifire.config_flow.UDPFireplaceFinder.search_fireplace"
    ):
        yield mock_found_fireplaces


@pytest.fixture
def mock_intellifire_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked IntelliFire client."""
    data_mock = Mock()
    data_mock.serial = "12345"

    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireAPILocal",
        autospec=True,
    ) as intellifire_mock:
        intellifire = intellifire_mock.return_value
        intellifire.data = data_mock
        yield intellifire


def mock_api_connection_error() -> ConnectionError:
    """Return a fake a ConnectionError for iftapi.net."""
    ret = ConnectionError()
    ret.args = [ConnectionKey("iftapi.net", 443, False, None, None, None, None)]
    return ret


@pytest.fixture
def mock_common_data_local() -> IntelliFireCommonFireplaceData:
    """Fixture for mock common data."""
    return IntelliFireCommonFireplaceData(
        auth_cookie="B984F21A6378560019F8A1CDE41B6782",
        user_id="52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        web_client_id="FA2B1C3045601234D0AE17D72F8E975",
        serial="3FB284769E4736F30C8973A7ED358123",
        api_key="B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        ip_address="192.168.2.108",
        read_mode=IntelliFireApiMode.LOCAL,
        control_mode=IntelliFireApiMode.LOCAL,
    )


@pytest.fixture
def mock_fp(mock_common_data_local):
    """Mock fireplace."""
    fixture_data = load_fixture("local_poll.json", DOMAIN)
    local_poll_json = IntelliFirePollData(**json.loads(fixture_data))

    assert local_poll_json.connection_quality == 988451

    with patch(
        "homeassistant.components.intellifire.__init__.UnifiedFireplace"
    ) as MockUnifiedFireplace:
        # Create an instance of the mock
        mock_instance = MockUnifiedFireplace.return_value

        # Mock methods and properties of the instance
        mock_instance.perform_cloud_poll = AsyncMock()
        mock_instance.perform_local_poll = AsyncMock()

        mock_instance.async_validate_connectivity = AsyncMock(return_value=(True, True))

        mock_instance.is_cloud_polling.return_value = False
        mock_instance.is_local_polling.return_value = True

        mock_instance.get_user_data_as_json.return_value = '{"mock": "data"}'

        mock_instance.ip_address = "192.168.1.100"
        mock_instance.api_key = "mock_api_key"
        mock_instance.serial = "mock_serial"
        mock_instance.user_id = "mock_user_id"
        mock_instance.auth_cookie = "mock_auth_cookie"
        mock_instance.web_client_id = "mock_web_client_id"

        mock_instance.read_api = MagicMock()  # If needed, you can mock this further
        mock_instance.control_api = MagicMock()  # If needed, you can mock this further

        # Connectivity
        mock_instance.local_connectivity = True
        mock_instance.cloud_connectivity = False

        mock_instance._read_mode = IntelliFireApiMode.LOCAL
        mock_instance.read_mode = IntelliFireApiMode.LOCAL

        mock_instance.control_mode = IntelliFireApiMode.LOCAL
        mock_instance._control_mode = IntelliFireApiMode.LOCAL

        # Use poll data locally
        mock_instance.data = local_poll_json

        mock_instance.set_read_mode = AsyncMock()
        mock_instance.set_control_mode = AsyncMock()

        mock_instance.async_validate_connectivity = AsyncMock(
            return_value=(True, False)
        )

        yield mock_instance  # Provide the mock instance to the test
