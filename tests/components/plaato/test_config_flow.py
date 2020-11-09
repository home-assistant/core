"""Test the Plaato config flow."""
from unittest.mock import patch

from pyplaato.models.device import PlaatoDeviceType
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.plaato import config_flow
from homeassistant.components.plaato.const import (
    CONF_CLOUDHOOK,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_USE_WEBHOOK,
    DOMAIN,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry

BASE_URL = "http://example.com"
WEBHOOK_ID = "webhook_id"
UNIQUE_ID = "plaato_unique_id"
CONF_UPDATE_INTERVAL = "update_interval"


@pytest.fixture(name="webhook_id")
def mock_webhook_id():
    """Mock webhook_id."""
    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ), patch(
        "homeassistant.components.webhook.async_generate_url", return_value="hook_id"
    ):
        yield


async def init_config_flow(hass):
    """Init a configuration flow."""
    await async_process_ha_core_config(
        hass,
        {"external_url": BASE_URL},
    )
    flow = config_flow.PlaatoConfigFlow()
    flow.hass = hass
    return flow


async def test_show_config_form(hass):
    """Test show configuration form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_show_config_form_device_type_airlock(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={
            CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
            CONF_DEVICE_NAME: "device_name",
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "api_method"
    assert result["data_schema"].schema.get(CONF_TOKEN) == str
    assert result["data_schema"].schema.get(CONF_USE_WEBHOOK) == bool


async def test_show_config_form_device_type_keg(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={CONF_DEVICE_TYPE: PlaatoDeviceType.Keg, CONF_DEVICE_NAME: "device_name"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "api_method"
    assert result["data_schema"].schema.get(CONF_TOKEN) == str
    assert result["data_schema"].schema.get(CONF_USE_WEBHOOK) is None


async def test_show_config_form_validate_webhook(hass, webhook_id):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_USE_WEBHOOK: True,
        CONF_TOKEN: "",
    }

    async def return_async_value(val):
        return val

    hass.config.components.add("cloud")
    with patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value=return_async_value("https://hooks.nabu.casa/ABCD"),
    ):
        result = await flow.async_step_webhook()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "webhook"

    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Keg,
        CONF_USE_WEBHOOK: True,
        CONF_TOKEN: "",
    }

    result = await flow.async_step_webhook()

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "api_method"
    assert len(flow._errors) == 1
    assert flow._errors["base"] == "invalid_webhook_device"


async def test_show_config_form_validate_token(hass):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_USE_WEBHOOK: False,
        CONF_TOKEN: "token",
        CONF_DEVICE_NAME: "device_name",
    }

    with patch("homeassistant.components.plaato.async_setup_entry", return_value=True):
        result = await flow.async_step_webhook()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == PlaatoDeviceType.Airlock.name
    assert result["data"] == {
        CONF_TOKEN: "token",
        CONF_USE_WEBHOOK: False,
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_DEVICE_NAME: "device_name",
    }


async def test_show_config_form_api_method(hass, webhook_id):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}

    # Using Airlock
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_DEVICE_NAME: "device_name",
    }
    result = await flow.async_step_api_method(
        user_input={CONF_USE_WEBHOOK: True, CONF_TOKEN: None}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "webhook"
    assert len(flow._errors) == 0


async def test_show_config_form_api_method_no_auth_token(hass, webhook_id):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}

    # Using Airlock
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_DEVICE_NAME: "device_name",
    }
    result = await flow.async_step_api_method(
        user_input={CONF_USE_WEBHOOK: False, CONF_TOKEN: None}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "api_method"
    assert len(flow._errors) == 1
    assert flow._errors["base"] == "no_api_method"

    # Using Keg
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Keg,
        CONF_DEVICE_NAME: "device_name",
    }
    result = await flow.async_step_api_method(
        user_input={CONF_USE_WEBHOOK: False, CONF_TOKEN: None}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "api_method"
    assert len(flow._errors) == 1
    assert flow._errors["base"] == "no_auth_token"


async def test_show_config_form_webhook(hass):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_USE_WEBHOOK: True,
        CONF_DEVICE_NAME: "device_name",
        CONF_TOKEN: None,
        CONF_WEBHOOK_ID: WEBHOOK_ID,
        CONF_CLOUDHOOK: WEBHOOK_ID,
    }

    with patch("homeassistant.components.plaato.async_setup_entry", return_value=True):
        result = await flow.async_step_webhook(
            user_input={
                CONF_WEBHOOK_ID: WEBHOOK_ID,
                CONF_CLOUDHOOK: WEBHOOK_ID,
            }
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == PlaatoDeviceType.Airlock.name
    assert result["data"] == {
        CONF_TOKEN: None,
        CONF_USE_WEBHOOK: True,
        CONF_WEBHOOK_ID: WEBHOOK_ID,
        CONF_CLOUDHOOK: WEBHOOK_ID,
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_DEVICE_NAME: "device_name",
    }


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NAME",
        data={},
        options={CONF_UPDATE_INTERVAL: 5},
    )

    flow = await init_config_flow(hass)
    flow.context = {}
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("homeassistant.components.plaato.async_setup_entry", return_value=True):
        result = await options_flow.async_step_user({CONF_UPDATE_INTERVAL: 10})

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_UPDATE_INTERVAL] == 10


async def test_options_webhook(hass, webhook_id):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="NAME",
        data={CONF_USE_WEBHOOK: True, CONF_WEBHOOK_ID: None},
        options={CONF_UPDATE_INTERVAL: 5},
    )

    flow = await init_config_flow(hass)
    flow.context = {}
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "webhook"
    assert result["description_placeholders"] == {"webhook_url": ""}

    with patch("homeassistant.components.plaato.async_setup_entry", return_value=True):
        result = await options_flow.async_step_webhook({CONF_WEBHOOK_ID: WEBHOOK_ID})

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_WEBHOOK_ID] == CONF_WEBHOOK_ID
