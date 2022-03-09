"""Test the Fibaro config flow."""
from unittest.mock import MagicMock, patch

from fiblary3.common.exceptions import HTTPException
import pytest

from homeassistant import config_entries
from homeassistant.components.fibaro import DOMAIN
from homeassistant.components.fibaro.const import CONF_IMPORT_PLUGINS
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

TEST_SERIALNUMBER = "HC2-111111"
TEST_NAME = "my_fibaro_home_center"
TEST_URL = "http://192.168.1.1/api/"
TEST_USERNAME = "user"
TEST_PASSWORD = "password"


@pytest.fixture(name="fibaro_client", autouse=True)
def fibaro_client_fixture():
    """Mock fibaro client."""
    login_obj_get = MagicMock()
    login_obj_get.status = True
    login_obj = MagicMock()
    login_obj.get.return_value = login_obj_get

    info_obj_get = MagicMock()
    info_obj_get.serialNumber = TEST_SERIALNUMBER
    info_obj_get.hcName = TEST_NAME
    info_obj = MagicMock()
    info_obj.get.return_value = info_obj_get

    array_obj = MagicMock()
    array_obj.get.return_value = []

    with patch("fiblary3.client.v4.client.Client.__init__", return_value=None,), patch(
        "fiblary3.client.v4.client.Client.login",
        login_obj,
        create=True,
    ), patch("fiblary3.client.v4.client.Client.info", info_obj, create=True,), patch(
        "fiblary3.client.v4.client.Client.rooms",
        return_value=array_obj,
        create=True,
    ), patch(
        "fiblary3.client.v4.client.Client.devices",
        return_value=array_obj,
        create=True,
    ), patch(
        "fiblary3.client.v4.client.Client.scenes",
        return_value=array_obj,
        create=True,
    ):
        yield


@pytest.fixture(name="fibaro_async_setup", autouse=True)
def fibaro_async_setup_fixture():
    """Mock fibaro setup."""
    with patch(
        "homeassistant.components.fibaro.async_setup_entry",
        return_value=True,
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

    with patch(
        "homeassistant.components.fibaro.FibaroController.connect",
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


async def test_config_flow_user_initiated_auth_failure(hass):
    """Authentication failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fibaro.FibaroController.connect",
        side_effect=HTTPException(details="Forbidden"),
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

    with patch(
        "homeassistant.components.fibaro.FibaroController.connect",
        side_effect=HTTPException(details="Any"),
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
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_user_initiated_unknown_failure_2(hass):
    """Unknown failure in flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fibaro.FibaroController.connect",
        side_effect=Exception(),
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
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_import(hass):
    """Test for importing config from configuration.yaml."""
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
