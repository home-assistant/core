"""Test the Fibaro config flow."""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError

from homeassistant import config_entries
from homeassistant.components.fibaro import DOMAIN
from homeassistant.components.fibaro.config_flow import _normalize_url
from homeassistant.components.fibaro.const import CONF_IMPORT_PLUGINS
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_SERIALNUMBER = "HC2-111111"
TEST_NAME = "my_fibaro_home_center"
TEST_URL = "http://192.168.1.1/api/"
TEST_USERNAME = "user"
TEST_PASSWORD = "password"
TEST_VERSION = "4.360"

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(name="fibaro_client", autouse=True)
def fibaro_client_fixture():
    """Mock common methods and attributes of fibaro client."""
    info_mock = Mock()
    info_mock.return_value.serial_number = TEST_SERIALNUMBER
    info_mock.return_value.hc_name = TEST_NAME
    info_mock.return_value.current_version = TEST_VERSION

    client_mock = Mock()
    client_mock.base_url.return_value = TEST_URL

    with patch(
        "homeassistant.components.fibaro.FibaroClient.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fibaro.FibaroClient.read_info",
        info_mock,
        create=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroClient.read_rooms",
        return_value=[],
    ), patch(
        "homeassistant.components.fibaro.FibaroClient.read_devices",
        return_value=[],
    ), patch(
        "homeassistant.components.fibaro.FibaroClient.read_scenes",
        return_value=[],
    ), patch(
        "homeassistant.components.fibaro.FibaroClient._rest_client",
        client_mock,
        create=True,
    ):
        yield


async def test_config_flow_user_initiated_success(hass: HomeAssistant) -> None:
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

        assert result["type"] == "create_entry"
        assert result["title"] == TEST_NAME
        assert result["data"] == {
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_IMPORT_PLUGINS: False,
        }


async def test_config_flow_user_initiated_connect_failure(hass: HomeAssistant) -> None:
    """Connect failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_user_initiated_auth_failure(hass: HomeAssistant) -> None:
    """Authentication failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.side_effect = HTTPError(response=Mock(status_code=403))
    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_user_initiated_unknown_failure_1(
    hass: HomeAssistant,
) -> None:
    """Unknown failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.side_effect = HTTPError(response=Mock(status_code=500))
    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_user_initiated_unknown_failure_2(
    hass: HomeAssistant,
) -> None:
    """Unknown failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.side_effect = Exception()
    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Successful reauth flow initialized by the user."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        entry_id=TEST_SERIALNUMBER,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_IMPORT_PLUGINS: False,
        },
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "other_fake_password"},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"


async def test_reauth_connect_failure(hass: HomeAssistant) -> None:
    """Successful reauth flow initialized by the user."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        entry_id=TEST_SERIALNUMBER,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_IMPORT_PLUGINS: False,
        },
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.side_effect = Exception()
    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "other_fake_password"},
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_auth_failure(hass: HomeAssistant) -> None:
    """Successful reauth flow initialized by the user."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        entry_id=TEST_SERIALNUMBER,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_IMPORT_PLUGINS: False,
        },
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.side_effect = HTTPError(response=Mock(status_code=403))
    with patch(
        "homeassistant.components.fibaro.FibaroClient.connect", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "other_fake_password"},
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("url_path", ["/api/", "/api", "/", ""])
async def test_normalize_url(url_path: str) -> None:
    """Test that the url is normalized for different entered values."""
    assert _normalize_url(f"http://192.168.1.1{url_path}") == "http://192.168.1.1/api/"
