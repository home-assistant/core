"""Test the Homee config flow."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.homee import config_flow
from homeassistant.components.homee.const import CONF_ADD_HOMEE_DATA, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOMEE_ID, HOMEE_IP, TESTPASS, TESTUSER

from tests.common import MockConfigEntry


async def test_config_flow(
    hass: HomeAssistant,
    mock_homee: MagicMock,  # pylint: disable=unused-argument
    mock_setup_entry: AsyncMock,  # pylint: disable=unused-argument
) -> None:
    """Test the complete config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    expected = {
        "data_schema": config_flow.AUTH_SCHEMA,
        "description_placeholders": None,
        "errors": {},
        "flow_id": ANY,
        "handler": DOMAIN,
        "step_id": "user",
        "type": FlowResultType.FORM,
        "last_step": None,
        "preview": None,
    }
    assert result == expected

    flow_id = result["flow_id"]

    final_result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
            CONF_ADD_HOMEE_DATA: False,
        },
    )

    expected = {
        "type": FlowResultType.CREATE_ENTRY,
        "flow_id": flow_id,
        "handler": DOMAIN,
        "data": {"host": HOMEE_IP, "username": TESTUSER, "password": TESTPASS},
        "description": None,
        "description_placeholders": None,
        "context": {"source": "user", "unique_id": HOMEE_ID},
        "title": f"{HOMEE_ID} ({HOMEE_IP})",
        "minor_version": 1,
        "options": {
            "add_homee_data": False,
        },
        "version": 1,
        "result": ANY,
    }

    assert expected == final_result


@pytest.mark.parametrize(
    ("side_eff", "error"),
    [
        (config_flow.InvalidAuth, {"base": "invalid_auth"}),
        (config_flow.CannotConnect, {"base": "cannot_connect"}),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    side_eff: Exception,
    error: dict[str, str],
) -> None:
    """Test the config flow fails as expected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    flow_id = result["flow_id"]

    with patch(
        "homeassistant.components.homee.config_flow.validate_and_connect",
        side_effect=side_eff,
    ):
        final_result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_HOST: HOMEE_IP,
                CONF_USERNAME: TESTUSER,
                CONF_PASSWORD: TESTPASS,
                CONF_ADD_HOMEE_DATA: False,
            },
        )

    assert final_result["type"] == FlowResultType.FORM
    assert final_result["errors"] == error


async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_homee: MagicMock,  # pylint: disable=unused-argument
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: HOMEE_IP,
            CONF_USERNAME: TESTUSER,
            CONF_PASSWORD: TESTPASS,
            CONF_ADD_HOMEE_DATA: False,
        },
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
