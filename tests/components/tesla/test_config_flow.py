"""Test the Tesla config flow."""
import datetime
from unittest.mock import AsyncMock, patch

from aiohttp import web
import pytest
from teslajsonpy import TeslaException
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tesla.config_flow import (
    TeslaAuthorizationCallbackView,
    TeslaAuthorizationProxyView,
)
from homeassistant.components.tesla.const import (
    AUTH_CALLBACK_PATH,
    AUTH_PROXY_PATH,
    CONF_EXPIRATION,
    CONF_WAKE_ON_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    ERROR_URL_NOT_DETECTED,
    MIN_SCAN_INTERVAL,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    HTTP_NOT_FOUND,
    HTTP_UNAUTHORIZED,
)
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

HA_URL = "https://homeassistant.com"
TEST_USERNAME = "test-username"
TEST_TOKEN = "test-token"
TEST_ACCESS_TOKEN = "test-access-token"
TEST_VALID_EXPIRATION = datetime.datetime.now().timestamp() * 2
TEST_INVALID_EXPIRATION = 0


async def test_warning_form(hass):
    """Test we get the warning form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # "type": RESULT_TYPE_FORM,
    # "flow_id": self.flow_id,
    # "handler": self.handler,
    # "step_id": step_id,
    # "data_schema": data_schema,
    # "errors": errors,
    # "description_placeholders": description_placeholders,

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["handler"] == DOMAIN
    assert result["step_id"] == "user"
    assert result["data_schema"] == vol.Schema({})
    assert result["errors"] == {}
    assert result["description_placeholders"] == {}
    return result


async def test_reauth_warning_form(hass):
    """Test we get the warning form on reauth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )
    # "type": RESULT_TYPE_FORM,
    # "flow_id": self.flow_id,
    # "handler": self.handler,
    # "step_id": step_id,
    # "data_schema": data_schema,
    # "errors": errors,
    # "description_placeholders": description_placeholders,

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["handler"] == DOMAIN
    assert result["step_id"] == "user"
    assert result["data_schema"] == vol.Schema({})
    assert result["errors"] == {}
    assert result["description_placeholders"] == {}
    return result


async def test_external_url(hass):
    """Test we get the external url after submitting once."""
    result = await test_warning_form(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.get_url",
        return_value=HA_URL,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={},
        )
    # "type": RESULT_TYPE_EXTERNAL_STEP,
    # "flow_id": self.flow_id,
    # "handler": self.handler,
    # "step_id": step_id,
    # "url": url,
    # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["step_id"] == "check_proxy"
    callback_url: str = str(
        URL(HA_URL).with_path(AUTH_CALLBACK_PATH).with_query({"flow_id": flow_id})
    )
    assert result["url"] == str(
        URL(HA_URL)
        .with_path(AUTH_PROXY_PATH)
        .with_query({"config_flow_id": flow_id, "callback_url": callback_url})
    )
    assert result["description_placeholders"] is None
    return result


async def test_external_url_no_hass_url_exception(hass):
    """Test we handle case with no detectable hass external url."""
    result = await test_warning_form(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.get_url",
        side_effect=NoURLAvailableError,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={},
        )
    # "type": RESULT_TYPE_EXTERNAL_STEP,
    # "flow_id": self.flow_id,
    # "handler": self.handler,
    # "step_id": step_id,
    # "url": url,
    # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["handler"] == DOMAIN
    assert result["step_id"] == "user"
    assert result["data_schema"] == vol.Schema({})
    assert result["errors"] == {"base": ERROR_URL_NOT_DETECTED}
    assert result["description_placeholders"] == {}


async def test_external_url_callback(hass):
    """Test we get the processing of callback_url."""
    result = await test_external_url(hass)
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id=flow_id,
        user_input={
            CONF_USERNAME: TEST_USERNAME,
            CONF_TOKEN: TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_VALID_EXPIRATION,
        },
    )
    # "type": RESULT_TYPE_EXTERNAL_STEP_DONE,
    # "flow_id": self.flow_id,
    # "handler": self.handler,
    # "step_id": next_step_id,
    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP_DONE
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["step_id"] == "finish_oauth"
    return result


async def test_finish_oauth(hass):
    """Test config entry after finishing oauth."""
    result = await test_external_url_callback(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        return_value={
            "refresh_token": TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_VALID_EXPIRATION,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={},
        )
        # "version": self.VERSION,
        # "type": RESULT_TYPE_CREATE_ENTRY,
        # "flow_id": self.flow_id,
        # "handler": self.handler,
        # "title": title,
        # "data": data,
        # "description": description,
        # "description_placeholders": description_placeholders,
    assert result["version"] == 1
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {
        CONF_TOKEN: TEST_TOKEN,
        CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
        CONF_EXPIRATION: TEST_VALID_EXPIRATION,
    }
    assert result["description"] is None
    assert result["description_placeholders"] is None
    return result


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth error."""
    result = await test_external_url_callback(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        side_effect=TeslaException(code=HTTP_UNAUTHORIZED),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={},
        )
        # "type": RESULT_TYPE_ABORT,
        # "flow_id": flow_id,
        # "handler": handler,
        # "reason": reason,
        # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["reason"] == "invalid_auth"
    assert result["description_placeholders"] is None


async def test_form_login_failed(hass):
    """Test we handle invalid auth error."""
    result = await test_external_url_callback(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={},
        )
        # "type": RESULT_TYPE_ABORT,
        # "flow_id": flow_id,
        # "handler": handler,
        # "reason": reason,
        # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["reason"] == "login_failed"
    assert result["description_placeholders"] is None


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await test_external_url_callback(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        side_effect=TeslaException(code=HTTP_NOT_FOUND),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={},
        )
        # "type": RESULT_TYPE_ABORT,
        # "flow_id": flow_id,
        # "handler": handler,
        # "reason": reason,
        # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["reason"] == "cannot_connect"
    assert result["description_placeholders"] is None


async def test_form_repeat_identifier(hass):
    """Test we handle repeat identifiers.

    Repeats are identified if the title and tokens are identical. Otherwise they are replaced.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USERNAME,
        data={
            CONF_TOKEN: TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_VALID_EXPIRATION,
        },
        options=None,
    )
    entry.add_to_hass(hass)

    result = await test_external_url_callback(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        return_value={
            "refresh_token": TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_VALID_EXPIRATION,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={},
        )
        # "type": RESULT_TYPE_ABORT,
        # "flow_id": flow_id,
        # "handler": handler,
        # "reason": reason,
        # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["reason"] == "already_configured"
    assert result["description_placeholders"] is None


async def test_form_second_identifier(hass):
    """Test we can create another entry with a different name.

    Repeats are identified if the title and tokens are identical. Otherwise they are replaced.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OTHER_USERNAME",
        data={
            CONF_TOKEN: TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_VALID_EXPIRATION,
        },
        options=None,
    )
    entry.add_to_hass(hass)
    await test_finish_oauth(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_form_reauth(hass):
    """Test we handle reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USERNAME,
        data={
            CONF_TOKEN: TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_INVALID_EXPIRATION,
        },
        options=None,
    )
    entry.add_to_hass(hass)

    result = await test_external_url_callback(hass)
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.tesla.config_flow.TeslaAPI.connect",
        return_value={
            "refresh_token": TEST_TOKEN,
            CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
            CONF_EXPIRATION: TEST_VALID_EXPIRATION,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={
                # CONF_TOKEN: TEST_TOKEN,
                # CONF_ACCESS_TOKEN: TEST_ACCESS_TOKEN,
                # CONF_EXPIRATION: TEST_VALID_EXPIRATION,
            },
        )
        # "type": RESULT_TYPE_ABORT,
        # "flow_id": flow_id,
        # "handler": handler,
        # "reason": reason,
        # "description_placeholders": description_placeholders,
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["flow_id"] == flow_id
    assert result["handler"] == DOMAIN
    assert result["reason"] == "reauth_successful"
    assert result["description_placeholders"] is None


async def test_import(hass):
    """Test import step results in warning form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_PASSWORD: "test-password", CONF_USERNAME: "test-username"},
    )

    # "type": RESULT_TYPE_FORM,
    # "flow_id": self.flow_id,
    # "handler": self.handler,
    # "step_id": step_id,
    # "data_schema": data_schema,
    # "errors": errors,
    # "description_placeholders": description_placeholders,

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] == vol.Schema({})
    assert result["description_placeholders"] == {}


async def test_option_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 350, CONF_WAKE_ON_START: True},
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SCAN_INTERVAL: 350, CONF_WAKE_ON_START: True}


async def test_option_flow_defaults(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_WAKE_ON_START: DEFAULT_WAKE_ON_START,
    }


async def test_option_flow_input_floor(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: 1}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL,
        CONF_WAKE_ON_START: DEFAULT_WAKE_ON_START,
    }


async def test_callback_view_invalid_query(hass, aiohttp_client):
    """Test callback view with invalid query."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()

    hass.http.register_view(TeslaAuthorizationCallbackView)

    client = await aiohttp_client(hass.http.app)

    resp = await client.get(AUTH_CALLBACK_PATH)
    assert resp.status == 400

    resp = await client.get(
        AUTH_CALLBACK_PATH, params={"api_password": "test-password"}
    )
    assert resp.status == 400

    # https://alandtse-test.duckdns.org/auth/tesla/callback?flow_id=7c0bdd32efca42c9bc8ce9c27f431f12&code=67443912fda4a307767a47081c55085650db40069aabd293da57185719c2&username=alandtse@gmail.com&domain=auth.tesla.com
    resp = await client.get(AUTH_CALLBACK_PATH, params={"flow_id": 1234})
    assert resp.status == 400

    with patch(
        "homeassistant.components.tesla.async_setup_entry", side_effect=KeyError
    ):
        resp = await client.get(AUTH_CALLBACK_PATH, params={"flow_id": 1234})
        assert resp.status == 400


async def test_callback_view_keyerror(hass, aiohttp_client):
    """Test callback view with keyerror."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()

    hass.http.register_view(TeslaAuthorizationCallbackView)

    client = await aiohttp_client(hass.http.app)

    with patch(
        "homeassistant.components.tesla.async_setup_entry", side_effect=KeyError
    ):
        resp = await client.get(AUTH_CALLBACK_PATH, params={"flow_id": 1234})
        assert resp.status == 400


async def test_callback_view_unknownflow(hass, aiohttp_client):
    """Test callback view with unknownflow."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()

    hass.http.register_view(TeslaAuthorizationCallbackView)

    client = await aiohttp_client(hass.http.app)

    with patch(
        "homeassistant.components.tesla.async_setup_entry", side_effect=UnknownFlow
    ):
        resp = await client.get(AUTH_CALLBACK_PATH, params={"flow_id": 1234})
        assert resp.status == 400


async def test_callback_view_success(hass, aiohttp_client):
    """Test callback view with success response."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()

    hass.http.register_view(TeslaAuthorizationCallbackView)

    result = await test_external_url(hass)
    flow_id = result["flow_id"]

    client = await aiohttp_client(hass.http.app)

    with patch("homeassistant.components.tesla.async_setup_entry", return_value=True):
        resp = await client.get(AUTH_CALLBACK_PATH, params={"flow_id": flow_id})
        assert resp.status == 200
        assert (
            "<script>window.close()</script>Success! This window can be closed"
            in await resp.text()
        )


@pytest.fixture
async def proxy_view(hass):
    """Generate registered proxy_view fixture."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_start()

    mock_handler = AsyncMock(return_value=web.Response(text="Success"))
    proxy_view = TeslaAuthorizationProxyView(mock_handler)
    hass.http.register_view(proxy_view)
    return proxy_view


@pytest.fixture
async def proxy_view_with_flow(hass, proxy_view):
    """Generate registered proxy_view fixture with running flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow_id = result["flow_id"]
    return flow_id


async def test_proxy_view_invalid_auth(hass, aiohttp_client, proxy_view):
    """Test proxy view request results in auth error."""

    client = await aiohttp_client(hass.http.app)

    for method in ("get", "post", "delete", "put", "patch", "head", "options"):
        resp = await getattr(client, method)(AUTH_PROXY_PATH)
        assert resp.status in [403, 401]


async def test_proxy_view_valid_auth_get(hass, aiohttp_client, proxy_view_with_flow):
    """Test proxy view get request results in valid response."""
    flow_id = proxy_view_with_flow

    client = await aiohttp_client(hass.http.app)

    resp = await client.get(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200


async def test_proxy_view_valid_auth_post(hass, aiohttp_client, proxy_view_with_flow):
    """Test proxy view post request results in valid response."""
    flow_id = proxy_view_with_flow

    client = await aiohttp_client(hass.http.app)

    resp = await client.post(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200


async def test_proxy_view_valid_auth_delete(hass, aiohttp_client, proxy_view_with_flow):
    """Test proxy view delete request results in valid response."""
    flow_id = proxy_view_with_flow

    client = await aiohttp_client(hass.http.app)

    resp = await client.delete(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200


async def test_proxy_view_valid_auth_put(hass, aiohttp_client, proxy_view_with_flow):
    """Test proxy view put request results in valid response."""
    flow_id = proxy_view_with_flow
    client = await aiohttp_client(hass.http.app)

    resp = await client.put(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200


async def test_proxy_view_valid_auth_patch(hass, aiohttp_client, proxy_view_with_flow):
    """Test proxy view patch request results in valid response."""
    flow_id = proxy_view_with_flow
    client = await aiohttp_client(hass.http.app)

    resp = await client.patch(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200


async def test_proxy_view_valid_auth_head(hass, aiohttp_client, proxy_view_with_flow):
    """Test proxy view head request results in valid response."""
    flow_id = proxy_view_with_flow
    client = await aiohttp_client(hass.http.app)

    resp = await client.head(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200


async def test_proxy_view_valid_auth_options(
    hass, aiohttp_client, proxy_view_with_flow
):
    """Test proxy view options request results in valid response."""
    flow_id = proxy_view_with_flow
    client = await aiohttp_client(hass.http.app)

    resp = await client.options(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 403


async def test_proxy_view_invalid_auth_after_reset(
    hass, aiohttp_client, proxy_view, proxy_view_with_flow
):
    """Test proxy view request results in invalid auth response after reset."""
    flow_id = proxy_view_with_flow
    client = await aiohttp_client(hass.http.app)

    resp = await client.get(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 200

    proxy_view.reset()
    hass.config_entries.flow.async_abort(flow_id)
    resp = await client.get(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 401

    resp = await client.post(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 401

    resp = await client.delete(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 401

    resp = await client.put(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 401

    resp = await client.patch(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 401

    resp = await client.head(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 401

    resp = await client.options(AUTH_PROXY_PATH, params={"config_flow_id": flow_id})
    assert resp.status == 403
