"""Tests for StarLine config flow."""
import requests_mock

from homeassistant import config_entries
from homeassistant.components.starline import config_flow

TEST_APP_ID = "666"
TEST_APP_SECRET = "appsecret"
TEST_APP_CODE = "appcode"
TEST_APP_TOKEN = "apptoken"
TEST_APP_SLNET = "slnettoken"
TEST_APP_SLID = "slidtoken"
TEST_APP_UID = "123"
TEST_APP_USERNAME = "sluser"
TEST_APP_PASSWORD = "slpassword"


async def test_flow_works(hass):
    """Test that config flow works."""
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://id.starline.ru/apiV3/application/getCode/",
            text='{"state": 1, "desc": {"code": "' + TEST_APP_CODE + '"}}',
        )
        mock.get(
            "https://id.starline.ru/apiV3/application/getToken/",
            text='{"state": 1, "desc": {"token": "' + TEST_APP_TOKEN + '"}}',
        )
        mock.post(
            "https://id.starline.ru/apiV3/user/login/",
            text='{"state": 1, "desc": {"user_token": "' + TEST_APP_SLID + '"}}',
        )
        mock.post(
            "https://developer.starline.ru/json/v2/auth.slid",
            text='{"code": 200, "user_id": "' + TEST_APP_UID + '"}',
            cookies={"slnet": TEST_APP_SLNET},
        )
        mock.get(
            "https://developer.starline.ru/json/v2/user/{}/user_info".format(
                TEST_APP_UID
            ),
            text='{"code": 200, "devices": [{"device_id": "123", "imei": "123", "alias": "123", "battery": "123", "ctemp": "123", "etemp": "123", "fw_version": "123", "gsm_lvl": "123", "phone": "123", "status": "1", "ts_activity": "123", "typename": "123", "balance": {}, "car_state": {}, "car_alr_state": {}, "functions": [], "position": {}}], "shared_devices": []}',
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "auth_app"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_APP_ID: TEST_APP_ID,
                config_flow.CONF_APP_SECRET: TEST_APP_SECRET,
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "auth_user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_USERNAME: TEST_APP_USERNAME,
                config_flow.CONF_PASSWORD: TEST_APP_PASSWORD,
            },
        )
        assert result["type"] == "create_entry"
        assert result["title"] == f"Application {TEST_APP_ID}"


async def test_step_auth_app_code_falls(hass):
    """Test config flow works when app auth code fails."""
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://id.starline.ru/apiV3/application/getCode/", text='{"state": 0}}'
        )
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                config_flow.CONF_APP_ID: TEST_APP_ID,
                config_flow.CONF_APP_SECRET: TEST_APP_SECRET,
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "auth_app"
        assert result["errors"] == {"base": "error_auth_app"}


async def test_step_auth_app_token_falls(hass):
    """Test config flow works when app auth token fails."""
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://id.starline.ru/apiV3/application/getCode/",
            text='{"state": 1, "desc": {"code": "' + TEST_APP_CODE + '"}}',
        )
        mock.get(
            "https://id.starline.ru/apiV3/application/getToken/", text='{"state": 0}'
        )
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                config_flow.CONF_APP_ID: TEST_APP_ID,
                config_flow.CONF_APP_SECRET: TEST_APP_SECRET,
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "auth_app"
        assert result["errors"] == {"base": "error_auth_app"}


async def test_step_auth_user_falls(hass):
    """Test config flow works when user fails."""
    with requests_mock.Mocker() as mock:
        mock.post("https://id.starline.ru/apiV3/user/login/", text='{"state": 0}')
        flow = config_flow.StarlineFlowHandler()
        flow.hass = hass
        result = await flow.async_step_auth_user(
            user_input={
                config_flow.CONF_USERNAME: TEST_APP_USERNAME,
                config_flow.CONF_PASSWORD: TEST_APP_PASSWORD,
            }
        )
        assert result["type"] == "form"
        assert result["step_id"] == "auth_user"
        assert result["errors"] == {"base": "error_auth_user"}
