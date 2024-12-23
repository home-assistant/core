"""Test the Homee config flow."""

from unittest.mock import ANY, MagicMock, patch

from pyHomee import HomeeAuthFailedException, HomeeConnectionFailedException
import pytest

from homeassistant.components.homee import config_flow
from homeassistant.components.homee.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import HOMEE_ID, HOMEE_IP, TESTPASS, TESTUSER

from tests.common import MockConfigEntry


async def test_config_flow(
    hass: HomeAssistant,
    mock_homee: MagicMock,  # pylint: disable=unused-argument
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
        },
    )

    assert final_result["type"] == FlowResultType.CREATE_ENTRY
    assert final_result["flow_id"] == flow_id
    assert final_result["handler"] == DOMAIN
    assert final_result["data"] == {
        "host": HOMEE_IP,
        "username": TESTUSER,
        "password": TESTPASS,
    }
    assert final_result["options"] == {}
    assert final_result["context"] == {
        "show_advanced_options": False,
        "source": "user",
        "unique_id": HOMEE_ID,
    }
    assert final_result["title"] == f"{HOMEE_ID} ({HOMEE_IP})"
    assert final_result["minor_version"] == 1
    assert final_result["version"] == 1


@pytest.mark.parametrize(
    ("side_eff", "error"),
    [
        (
            HomeeConnectionFailedException("connection timed out"),
            {"base": "cannot_connect"},
        ),
        (
            HomeeAuthFailedException("wrong username or password"),
            {"base": "invalid_auth"},
        ),
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
        "pyHomee.Homee.get_access_token",
        side_effect=side_eff,
    ):
        final_result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={
                CONF_HOST: HOMEE_IP,
                CONF_USERNAME: TESTUSER,
                CONF_PASSWORD: TESTPASS,
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
        },
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
