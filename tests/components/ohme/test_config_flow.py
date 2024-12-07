"""Tests for the config flow."""

from unittest import mock

from homeassistant.components.ohme import config_flow
from homeassistant.core import HomeAssistant


async def test_step_account(hass: HomeAssistant) -> None:
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
