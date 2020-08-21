"""Test the Plaato config flow."""
from unittest.mock import patch

from pyplaato.models.device import PlaatoDeviceType
import pytest

from homeassistant import config_entries, setup
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
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

BASE_URL = "http://example.com"
WEBHOOK_ID = "webhook_id"


@pytest.fixture(name="webhook_id")
def mock_webhook_id():
    """Mock webhook_id."""
    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ):
        yield


async def init_config_flow(hass):
    """Init a configuration flow."""
    await async_process_ha_core_config(
        hass, {"external_url": BASE_URL},
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
    assert result["step_id"] == "device_type"


async def test_show_config_form_device_type_airlock(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "device_type"},
        data={
            CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
            CONF_DEVICE_NAME: "device_name",
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "validate"
    assert result["data_schema"].schema.get(CONF_TOKEN) == str
    assert result["data_schema"].schema.get(CONF_USE_WEBHOOK) == bool


async def test_show_config_form_device_type_keg(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "device_type"},
        data={CONF_DEVICE_TYPE: PlaatoDeviceType.Keg, CONF_DEVICE_NAME: "device_name"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "validate"
    assert result["data_schema"].schema.get(CONF_TOKEN) == str
    assert result["data_schema"].schema.get(CONF_USE_WEBHOOK) is None


async def test_show_config_form_validate_webhook(hass, webhook_id):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow._init_info = {CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock}

    result = await flow.async_step_validate(
        user_input={CONF_USE_WEBHOOK: True, CONF_TOKEN: ""}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "webhook"

    flow._init_info = {CONF_DEVICE_TYPE: PlaatoDeviceType.Keg}

    result = await flow.async_step_validate(
        user_input={CONF_USE_WEBHOOK: True, CONF_TOKEN: ""}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "validate"
    assert len(flow._errors) == 1
    assert flow._errors["base"] == "invalid_webhook_device"


async def test_show_config_form_validate_token(hass):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}
    flow._init_info = {CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock}

    result = await flow.async_step_validate(
        user_input={CONF_USE_WEBHOOK: False, CONF_TOKEN: "token"}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == PlaatoDeviceType.Airlock.name
    assert result["data"] == {
        CONF_TOKEN: "token",
        CONF_USE_WEBHOOK: False,
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
    }


async def test_show_config_form_validate_no_device(hass):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}
    flow._init_info = {CONF_DEVICE_TYPE: None}

    result = await flow.async_step_validate(
        user_input={CONF_USE_WEBHOOK: False, CONF_TOKEN: "token"}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "no_device"


async def test_show_config_form_webhook(hass):
    """Test show configuration form."""

    flow = await init_config_flow(hass)
    flow.context = {}
    flow._init_info = {
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
        CONF_USE_WEBHOOK: True,
        CONF_WEBHOOK_ID: WEBHOOK_ID,
        CONF_CLOUDHOOK: WEBHOOK_ID,
    }

    result = await flow.async_step_webhook()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == PlaatoDeviceType.Airlock.name
    assert result["data"] == {
        CONF_USE_WEBHOOK: True,
        CONF_WEBHOOK_ID: WEBHOOK_ID,
        CONF_CLOUDHOOK: WEBHOOK_ID,
        CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
    }

    # with patch(
    #     "homeassistant.components.plaato.async_setup", return_value=True
    # ) as mock_setup, patch(
    #     "homeassistant.components.plaato.async_setup_entry", return_value=True,
    # ) as mock_setup_entry:
    #     MockConfigEntry(domain=DOMAIN, unique_id="token",
    #                     data={}).add_to_hass(
    #         hass
    #     )
    #
    #     result2 = await hass.config_entries.flow.async_configure(
    #         result["flow_id"],
    #         {
    #             CONF_TOKEN: "token",
    #             CONF_USE_WEBHOOK: False,
    #             CONF_WEBHOOK_ID: None,
    #             CONF_DEVICE_TYPE: PlaatoDeviceType.Airlock,
    #         },
    #     )


# async def test_form_source_user(hass):
#     """Test we get the form."""
#     await setup.async_setup_component(hass, "persistent_notification", {})
#     result = await hass.config_entries.flow.async_init(
#         DOMAIN, context={"source": config_entries.SOURCE_USER}
#     )
#     assert result["type"] == "form"
#     assert result["errors"] == {}
#
#     with patch(
#         "homeassistant.components.plaato.config_flow.PlaatoDeviceType",
#         return_value=True,
#     ), patch(
#         "homeassistant.components.plaato.async_setup", return_value=True
#     ) as mock_setup, patch(
#         "homeassistant.components.plaato.async_setup_entry", return_value=True,
#     ) as mock_setup_entry:
#         result2 = await hass.config_entries.flow.async_configure(
#             result["flow_id"],
#             {
#                 "host": "1.1.1.1",
#                 "username": "test-username",
#                 "password": "test-password",
#             },
#         )
#
#     assert result2["type"] == "create_entry"
#     assert result2["title"] == "Name of the device"
#     assert result2["data"] == {
#         "host": "1.1.1.1",
#         "username": "test-username",
#         "password": "test-password",
#     }
#     await hass.async_block_till_done()
#     assert len(mock_setup.mock_calls) == 1
#     assert len(mock_setup_entry.mock_calls) == 1
#
#
# def _mock_plaato_device_side_effect(site_info=None):
#     powerwall_mock = MagicMock(PlaatoDeviceType)
#     powerwall_mock.get_site_info = Mock(side_effect=site_info)
#     return powerwall_mock
