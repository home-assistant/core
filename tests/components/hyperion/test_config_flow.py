"""Tests for the Hyperion config flow."""

import logging

from homeassistant import data_entry_flow, setup
from homeassistant.components.hyperion.const import CONF_INSTANCE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT

from . import TEST_HOST, TEST_INSTANCE, TEST_PORT, create_mock_client

from tests.async_mock import patch

_LOGGER = logging.getLogger(__name__)


async def test_form_if_no_configuration(hass):
    """Check flow aborts when no configuration is present."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["handler"] == DOMAIN


async def test_noauth_flow_success(hass):
    """Check a full flow without auth."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    client = create_mock_client()
    user_input = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_INSTANCE: TEST_INSTANCE,
    }

    with patch("hyperion.client.HyperionClient", return_value=client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["handler"] == DOMAIN
    assert result["title"] == client.id
    assert result["data"] == user_input
