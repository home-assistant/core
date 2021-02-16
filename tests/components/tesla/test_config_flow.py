"""Test the Tesla config flow."""
import datetime
from unittest.mock import patch

from teslajsonpy import TeslaException
import voluptuous as vol
from yarl import URL

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tesla.const import (
    AUTH_CALLBACK_PATH,
    AUTH_PROXY_PATH,
    CONF_EXPIRATION,
    CONF_WAKE_ON_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    HTTP_NOT_FOUND,
)

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
    assert result["reason"] == "login_failed"
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
