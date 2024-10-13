"""Fixtures for IntelliFire integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

from intellifire4py.const import IntelliFireApiMode
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

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.intellifire.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_fireplace_finder_none() -> Generator[MagicMock]:
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
        minor_version=2,
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
        unique_id="3FB284769E4736F30C8973A7ED358123",
    )


@pytest.fixture
def mock_config_entry_old() -> MockConfigEntry:
    """For migration testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Fireplace 3FB284769E4736F30C8973A7ED358123",
        data={
            CONF_HOST: "192.168.2.108",
            CONF_USERNAME: "grumpypanda@china.cn",
            CONF_PASSWORD: "you-stole-my-pandas",
            CONF_USER_ID: "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        },
    )


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
def mock_apis_multifp(
    mock_cloud_interface, mock_local_interface, mock_fp
) -> Generator[tuple[AsyncMock, AsyncMock, MagicMock]]:
    """Multi fireplace version of mocks."""
    return mock_local_interface, mock_cloud_interface, mock_fp


@pytest.fixture
def mock_apis_single_fp(
    mock_cloud_interface, mock_local_interface, mock_fp
) -> Generator[tuple[AsyncMock, AsyncMock, MagicMock]]:
    """Single fire place version of the mocks."""
    data_v1 = IntelliFireUserData(
        **load_json_object_fixture("user_data_1.json", DOMAIN)
    )
    with patch.object(
        type(mock_cloud_interface), "user_data", new_callable=PropertyMock
    ) as mock_user_data:
        mock_user_data.return_value = data_v1
        yield mock_local_interface, mock_cloud_interface, mock_fp


@pytest.fixture
def mock_cloud_interface() -> Generator[AsyncMock]:
    """Mock cloud interface to use for testing."""
    user_data = IntelliFireUserData(
        **load_json_object_fixture("user_data_3.json", DOMAIN)
    )

    with (
        patch(
            "homeassistant.components.intellifire.IntelliFireCloudInterface",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.intellifire.config_flow.IntelliFireCloudInterface",
            new=mock_client,
        ),
        patch(
            "intellifire4py.cloud_interface.IntelliFireCloudInterface",
            new=mock_client,
        ),
    ):
        # Mock async context manager
        mock_client = mock_client.return_value
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock other async methods if needed
        mock_client.login_with_credentials = AsyncMock()
        mock_client.poll = AsyncMock()
        type(mock_client).user_data = PropertyMock(return_value=user_data)

        yield mock_client  # Yielding to the test


@pytest.fixture
def mock_local_interface() -> Generator[AsyncMock]:
    """Mock version of IntelliFireAPILocal."""
    poll_data = IntelliFirePollData(
        **load_json_object_fixture("intellifire/local_poll.json")
    )
    with patch(
        "homeassistant.components.intellifire.config_flow.IntelliFireAPILocal",
        autospec=True,
    ) as mock_client:
        mock_client = mock_client.return_value
        # Mock all instances of the class
        type(mock_client).data = PropertyMock(return_value=poll_data)
        yield mock_client


@pytest.fixture
def mock_fp(mock_common_data_local) -> Generator[AsyncMock]:
    """Mock fireplace."""

    local_poll_data = IntelliFirePollData(
        **load_json_object_fixture("local_poll.json", DOMAIN)
    )

    assert local_poll_data.connection_quality == 988451

    with patch(
        "homeassistant.components.intellifire.UnifiedFireplace"
    ) as mock_unified_fireplace:
        # Create an instance of the mock
        mock_instance = mock_unified_fireplace.return_value

        # Mock methods and properties of the instance
        mock_instance.perform_cloud_poll = AsyncMock()
        mock_instance.perform_local_poll = AsyncMock()

        mock_instance.async_validate_connectivity = AsyncMock(return_value=(True, True))

        type(mock_instance).is_cloud_polling = PropertyMock(return_value=False)
        type(mock_instance).is_local_polling = PropertyMock(return_value=True)

        mock_instance.get_user_data_as_json.return_value = '{"mock": "data"}'

        mock_instance.ip_address = "192.168.1.100"
        mock_instance.api_key = "mock_api_key"
        mock_instance.serial = "mock_serial"
        mock_instance.user_id = "mock_user_id"
        mock_instance.auth_cookie = "mock_auth_cookie"
        mock_instance.web_client_id = "mock_web_client_id"

        # Configure the READ Api
        mock_instance.read_api = MagicMock()
        mock_instance.read_api.poll = MagicMock(return_value=local_poll_data)
        mock_instance.read_api.data = local_poll_data

        mock_instance.control_api = MagicMock()

        mock_instance.local_connectivity = True
        mock_instance.cloud_connectivity = False

        mock_instance._read_mode = IntelliFireApiMode.LOCAL
        mock_instance.read_mode = IntelliFireApiMode.LOCAL

        mock_instance.control_mode = IntelliFireApiMode.LOCAL
        mock_instance._control_mode = IntelliFireApiMode.LOCAL

        mock_instance.data = local_poll_data

        mock_instance.set_read_mode = AsyncMock()
        mock_instance.set_control_mode = AsyncMock()

        mock_instance.async_validate_connectivity = AsyncMock(
            return_value=(True, False)
        )

        # Patch class methods
        with patch(
            "homeassistant.components.intellifire.UnifiedFireplace.build_fireplace_from_common",
            new_callable=AsyncMock,
            return_value=mock_instance,
        ):
            yield mock_instance
