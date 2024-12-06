"""Tests for the config flow."""

from unittest import mock
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_PATH
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ohme import config_flow
from custom_components.ohme.const import DOMAIN


async def test_step_account(hass):
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    expected = {
        "type": "form",
        "flow_id": mock.ANY,
        "handler": "ohme",
        "step_id": "user",
        "data_schema": config_flow.USER_SCHEMA,
        "errors": {},
        "description_placeholders": None,
        "last_step": None,
        "preview": None,
    }

    assert expected == result
