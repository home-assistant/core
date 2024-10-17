"""Define integration configuration flow tests for the Duwi integration."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.duwi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

import pytest
from syrupy.assertion import SnapshotAssertion


@pytest.mark.usefixtures(
    "mock_duwi_login_user", "mock_duwi_login_auth", "mock_duwi_login_select_house"
)
async def test_user_flow_success(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow: successful path.

    This simulates a user going through the configuration flow, including
    providing correct credentials and selecting a house, leading to a successful
    creation of a config entry.
    """
    # Start by initializing the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    # Ensure we're being prompted for initial information
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Simulate submitting the app credentials step
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"app_key": "correct_app_key", "app_secret": "correct_app_secret"},
    )
    # Ensure the next step is the authentication stage
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "auth"

    # Next, simulate submitting the phone and password
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"phone": "correct_phone", "password": "correct_password"},
    )
    # Move to selecting a house
    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == "select_house"

    # Finally, simulate selecting a house
    result4 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"house_no": "house_nos_123"},
    )
    # The flow should now complete with a CREATE_ENTRY result
    assert result4.get("type") == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_duwi_login_user")
async def test_user_flow_user_failed(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow: invalid user input.

    This simulates the user providing incorrect app credentials,
    which should result in repeating the initial user step.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"app_key": "error_app_key", "app_secret": "error_app_secret"},
    )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"


@pytest.mark.usefixtures("mock_duwi_login_user", "mock_duwi_login_auth")
async def test_user_flow_auth_failed(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow: failed authentication.

    This tests the flow where the user enters correct app credentials,
    but fails at the authentication (login) step.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == config_entries.SOURCE_USER
    snapshot.assert_match(result)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"app_key": "correct_app_key", "app_secret": "correct_app_secret"},
    )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "auth"
    snapshot.assert_match(result2)

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"phone": "error_phone", "password": "error_password"},
    )
    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == "auth"
    snapshot.assert_match(result3)
