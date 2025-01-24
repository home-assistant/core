"""Test the aidot config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.aidot.config_flow import CannotConnect, InvalidHost
from homeassistant.components.aidot.const import (
    CONF_CHOOSE_HOUSE,
    CONF_PASSWORD,
    CONF_SERVER_COUNTRY,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_COUNTRY, TEST_EMAIL, TEST_PASSWORD

TEST_HOME = "Test Home"
TEST_LOGIN_RESPONSE = {
    "id": "314159263367458941151",
    "accessToken": "1234567891011121314151617181920",
    "refreshToken": "2021222324252627282930313233343",
    "expiresIn": 10000,
    "nickname": TEST_EMAIL,
    "username": TEST_EMAIL,
}

TEST_HOUSES = [
    {
        "id": "123456789",
        "name": TEST_HOME,
        "isDefault": True,
        "isOwner": True,
        "owner": "a9d9dee885994b9fb46bba328ef6e808",
        "roomCount": "1",
        "deviceCount": "1",
    }
]

TEST_HOUSES2 = [
    {
        "id": "123456789",
        "name": TEST_HOME,
        "isDefault": True,
        "isOwner": True,
        "owner": "a9d9dee885994b9fb46bba328ef6e808",
        "roomCount": "1",
        "deviceCount": "1",
    },
    {
        "id": "123456780",
        "name": "Test Home1",
        "isDefault": True,
        "isOwner": True,
        "owner": "a9d9dee885994b9fb46bba328ef6e809",
        "roomCount": "1",
        "deviceCount": "1",
    },
]

TEST_DEVICE_LIST = [
    {
        "id": "1592778822313467906",
        "name": "Test Device",
        "type": "light",
        "aesKey": "1111111111111111",
        "categoryId": "3",
        "modelId": "LK.light.test1",
        "isDirectDevice": 1,
        "productId": "123456",
    }
]

TEST_PRODUCT_LIST = [
    {
        "modelId": "LK.light.test",
        "isDirectDevice": 1,
        "powerType": 0,
        "serviceModules": [
            {"identity": "control.light.effect.mode"},
            {"identity": "control.light.rgbw"},
            {"identity": "control.light.cct"},
            {"identity": "control.light.dimming"},
        ],
    }
]


@pytest.fixture(name="aidot_login", autouse=True)
def aidot_login_fixture():
    """Aidot and entry setup."""
    with (
        patch(
            "homeassistant.components.aidot.config_flow.LoginControl.async_post_login",
            return_value=TEST_LOGIN_RESPONSE,
        ),
        patch(
            "homeassistant.components.aidot.config_flow.LoginControl.async_get_houses",
            return_value=TEST_HOUSES,
        ),
        patch(
            "homeassistant.components.aidot.config_flow.LoginControl.async_get_devices",
            return_value=TEST_DEVICE_LIST,
        ),
        patch(
            "homeassistant.components.aidot.config_flow.LoginControl.async_get_products",
            return_value=TEST_PRODUCT_LIST,
        ),
        patch("homeassistant.components.aidot.async_setup_entry", return_value=True),
        patch("homeassistant.components.aidot.async_unload_entry", return_value=True),
    ):
        yield


async def test_config_flow_user_init(hass: HomeAssistant) -> None:
    """Test a failed config flow user init."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_config_flow_cloud_login_success(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud login success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["errors"] == {}


async def test_config_flow_cloud_get_houses(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud get houses."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["errors"] == {}


async def test_config_flow_cloud_multi_houses(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud multi houses choose."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_get_houses",
        return_value=TEST_HOUSES2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERVER_COUNTRY: TEST_COUNTRY,
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
    houses_name = [item["name"] for item in TEST_HOUSES2]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["data_schema"].schema["choose_house"].container == houses_name


async def test_config_flow_cloud_get_device_list(hass: HomeAssistant) -> None:
    """Test a successful config flow using cloud devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CHOOSE_HOUSE: TEST_HOME,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL + " " + TEST_HOME
    assert result["data"] == {
        "login_response": TEST_LOGIN_RESPONSE,
        "selected_house": TEST_HOUSES[0],
        "device_list": TEST_DEVICE_LIST,
        "product_list": TEST_PRODUCT_LIST,
    }


async def test_config_flow_cloud_not_devices(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud with no devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_get_devices",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CHOOSE_HOUSE: TEST_HOME,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL + " " + TEST_HOME
    assert result["data"]["device_list"] == []


async def test_config_flow_cloud_not_houses(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud with no houses."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_get_houses",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERVER_COUNTRY: TEST_COUNTRY,
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "get_house_failed"}


async def test_config_flow_cloud_not_products(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud with no products."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_get_products",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CHOOSE_HOUSE: TEST_HOME,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL + " " + TEST_HOME
    assert result["data"] == {
        "login_response": TEST_LOGIN_RESPONSE,
        "selected_house": TEST_HOUSES[0],
        "device_list": TEST_DEVICE_LIST,
        "product_list": [],
    }


async def test_config_flow_cloud_mission_token(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud with no devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_house"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_get_devices",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CHOOSE_HOUSE: TEST_HOME,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["device_list"] is None


async def test_async_show_country_form(hass: HomeAssistant) -> None:
    """Test that async_show_form is called with correct parameters in user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    TEST_SERVERS = [{"name": "United States"}, {"name": "Canada"}]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.aidot.config_flow.CLOUD_SERVERS",
        TEST_SERVERS,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
        )
    counties_name = [item["name"] for item in TEST_SERVERS]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"].schema["server_country"].container == counties_name


async def test_config_flow_cloud_login_failed(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud login failed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_post_login",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERVER_COUNTRY: TEST_COUNTRY,
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "login_failed"}


async def test_config_flow_cloud_connect_error(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_post_login",
        side_effect=CannotConnect(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERVER_COUNTRY: TEST_COUNTRY,
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_cloud_invalid_host(hass: HomeAssistant) -> None:
    """Test a failed config flow using cloud invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl.async_post_login",
        side_effect=InvalidHost(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERVER_COUNTRY: TEST_COUNTRY,
                CONF_USERNAME: TEST_EMAIL,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"host": "cannot_connect"}
