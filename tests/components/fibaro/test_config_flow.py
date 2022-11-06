"""Test the Fibaro config flow."""
from unittest.mock import Mock, patch

from fiblary3.common.exceptions import HTTPException
import pytest

from homeassistant import config_entries
from homeassistant.components.fibaro import DOMAIN
from homeassistant.components.fibaro.const import CONF_IMPORT_PLUGINS
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from tests.common import MockConfigEntry

TEST_SERIALNUMBER = "HC2-111111"
TEST_NAME = "my_fibaro_home_center"
TEST_URL = "http://192.168.1.1/api/"
TEST_USERNAME = "user"
TEST_PASSWORD = "password"
TEST_VERSION = "4.360"


@pytest.fixture(name="fibaro_client", autouse=True)
def fibaro_client_fixture():
    """Mock common methods and attributes of fibaro client."""
    info_mock = Mock()
    info_mock.get.return_value = Mock(
        serialNumber=TEST_SERIALNUMBER, hcName=TEST_NAME, softVersion=TEST_VERSION
    )

    array_mock = Mock()
    array_mock.list.return_value = []

    client_mock = Mock()
    client_mock.base_url.return_value = TEST_URL

    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fibaro.FibaroClientV4.info",
        info_mock,
        create=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroClientV4.rooms",
        array_mock,
        create=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroClientV4.devices",
        array_mock,
        create=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroClientV4.scenes",
        array_mock,
        create=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroClientV4.client",
        client_mock,
        create=True,
    ):
        yield


async def test_config_flow_user_initiated_success(hass):
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.get.return_value = Mock(status=True)
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
    ), patch(
        "homeassistant.components.fibaro.async_setup_entry",
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


async def test_config_flow_user_initiated_connect_failure(hass):
    """Connect failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.get.return_value = Mock(status=False)
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
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


async def test_config_flow_user_initiated_auth_failure(hass):
    """Authentication failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.get.side_effect = HTTPException(details="Forbidden")
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
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


async def test_config_flow_user_initiated_unknown_failure_1(hass):
    """Unknown failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    login_mock = Mock()
    login_mock.get.side_effect = HTTPException(details="Any")
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
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


async def test_config_flow_user_initiated_unknown_failure_2(hass):
    """Unknown failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

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


async def test_config_flow_import(hass):
    """Test for importing config from configuration.yaml."""
    login_mock = Mock()
    login_mock.get.return_value = Mock(status=True)
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
    ), patch(
        "homeassistant.components.fibaro.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_URL: TEST_URL,
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
                CONF_IMPORT_PLUGINS: False,
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


async def test_reauth_success(hass):
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
    login_mock.get.return_value = Mock(status=True)
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
    ), patch(
        "homeassistant.components.fibaro.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "other_fake_password"},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"


async def test_reauth_connect_failure(hass):
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
    login_mock.get.return_value = Mock(status=False)
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "other_fake_password"},
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_auth_failure(hass):
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
    login_mock.get.side_effect = HTTPException(details="Forbidden")
    with patch(
        "homeassistant.components.fibaro.FibaroClientV4.login", login_mock, create=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "other_fake_password"},
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}
