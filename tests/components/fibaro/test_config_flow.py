"""Test the Fibaro config flow."""
from unittest.mock import patch

from fiblary3.common.exceptions import HTTPException
import pytest

from homeassistant import config_entries
from homeassistant.components.fibaro import DOMAIN
from homeassistant.components.fibaro.const import CONF_IMPORT_PLUGINS
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

TEST_SERIALNUMBER = "HC2-111111"
TEST_NAME = "My fibaro home center"
TEST_URL = "http://192.168.1.1/api/"
TEST_USERNAME = "user"
TEST_PASSWORD = "password"


@pytest.fixture(name="fibaro_controller", autouse=True)
def fibaro_controller_fixture():
    """Mock fibaro controller."""
    with patch(
        "homeassistant.components.fibaro.FibaroController.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fibaro.FibaroController.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroController.hub_serial",
        TEST_SERIALNUMBER,
        create=True,
    ), patch(
        "homeassistant.components.fibaro.FibaroController.name",
        TEST_NAME,
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
    """Connect failure in flow manually initialized by the user."""
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


async def test_config_flow_user_initiated_unknonw_failure_1(hass):
    """Connect failure in flow manually initialized by the user."""
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
    """Connect failure in flow manually initialized by the user."""
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
    """Connect failure in flow manually initialized by the user."""
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
