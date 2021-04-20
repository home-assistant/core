"""Tests for OwnTracks config flow."""
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.owntracks import config_flow
from homeassistant.components.owntracks.config_flow import CONF_CLOUDHOOK, CONF_SECRET
from homeassistant.components.owntracks.const import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CONF_WEBHOOK_URL = "webhook_url"

BASE_URL = "http://example.com"
CLOUDHOOK = False
SECRET = "test-secret"
WEBHOOK_ID = "webhook_id"
WEBHOOK_URL = f"{BASE_URL}/api/webhook/webhook_id"


@pytest.fixture(name="webhook_id")
def mock_webhook_id():
    """Mock webhook_id."""
    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ):
        yield


@pytest.fixture(name="secret")
def mock_secret():
    """Mock secret."""
    with patch("secrets.token_hex", return_value=SECRET):
        yield


@pytest.fixture(name="not_supports_encryption")
def mock_not_supports_encryption():
    """Mock non successful nacl import."""
    with patch(
        "homeassistant.components.owntracks.config_flow.supports_encryption",
        return_value=False,
    ):
        yield


async def init_config_flow(hass):
    """Init a configuration flow."""
    await async_process_ha_core_config(
        hass,
        {"external_url": BASE_URL},
    )
    flow = config_flow.OwnTracksFlow()
    flow.hass = hass
    return flow


async def test_user(hass, webhook_id, secret):
    """Test user step."""
    flow = await init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "OwnTracks"
    assert result["data"][CONF_WEBHOOK_ID] == WEBHOOK_ID
    assert result["data"][CONF_SECRET] == SECRET
    assert result["data"][CONF_CLOUDHOOK] == CLOUDHOOK
    assert result["description_placeholders"][CONF_WEBHOOK_URL] == WEBHOOK_URL


async def test_import(hass, webhook_id, secret):
    """Test import step."""
    flow = await init_config_flow(hass)

    result = await flow.async_step_import({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "OwnTracks"
    assert result["data"][CONF_WEBHOOK_ID] == WEBHOOK_ID
    assert result["data"][CONF_SECRET] == SECRET
    assert result["data"][CONF_CLOUDHOOK] == CLOUDHOOK
    assert result["description_placeholders"] is None


async def test_import_setup(hass):
    """Test that we automatically create a config flow."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com"},
    )

    assert not hass.config_entries.async_entries(DOMAIN)
    assert await async_setup_component(hass, DOMAIN, {"owntracks": {}})
    await hass.async_block_till_done()
    assert hass.config_entries.async_entries(DOMAIN)


async def test_abort_if_already_setup(hass):
    """Test that we can't add more than one instance."""
    flow = await init_config_flow(hass)

    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)
    assert hass.config_entries.async_entries(DOMAIN)

    # Should fail, already setup (import)
    result = await flow.async_step_import({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"

    # Should fail, already setup (flow)
    result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_not_supports_encryption(hass, not_supports_encryption):
    """Test user step."""
    flow = await init_config_flow(hass)

    result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert (
        result["description_placeholders"]["secret"]
        == "Encryption is not supported because nacl is not installed."
    )


async def test_unload(hass):
    """Test unloading a config flow."""
    await async_process_ha_core_config(
        hass,
        {"external_url": "http://example.com"},
    )

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup"
    ) as mock_forward:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={}
        )

    assert len(mock_forward.mock_calls) == 1
    entry = result["result"]

    assert mock_forward.mock_calls[0][1][0] is entry
    assert mock_forward.mock_calls[0][1][1] == "device_tracker"
    assert entry.data["webhook_id"] in hass.data["webhook"]

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=None,
    ) as mock_unload:
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert len(mock_unload.mock_calls) == 1
    assert mock_forward.mock_calls[0][1][0] is entry
    assert mock_forward.mock_calls[0][1][1] == "device_tracker"
    assert entry.data["webhook_id"] not in hass.data["webhook"]


async def test_with_cloud_sub(hass):
    """Test creating a config flow while subscribed."""
    hass.config.components.add("cloud")
    with patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook",
        return_value="https://hooks.nabu.casa/ABCD",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data={}
        )

    entry = result["result"]
    assert entry.data["cloudhook"]
    assert (
        result["description_placeholders"]["webhook_url"]
        == "https://hooks.nabu.casa/ABCD"
    )
