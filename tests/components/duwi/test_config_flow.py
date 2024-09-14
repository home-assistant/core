"""Define integration configuration flow tests for the Duwi integration."""

from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.duwi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_duwi_login_user", "mock_duwi_login_and_fetch_house")
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
    snapshot.assert_match(result)

    # Simulate submitting the app credentials step
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "app_key": "correct_app_key",
            "app_secret": "correct_app_secret",
            "phone": "correct_phone",
            "password": "correct_password",
        },
    )

    # Move to selecting a house
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "select_house"
    snapshot.assert_match(result2)

    # Finally, simulate selecting a house
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"house_no": "mocked_house_no1"},
    )
    # The flow should now complete with a CREATE_ENTRY result
    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    snapshot.assert_match(result3)


@pytest.mark.usefixtures("mock_duwi_login_user", "mock_duwi_login_and_fetch_house")
async def test_user_flow_failed_by_phone_auth(
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
        user_input={
            "app_key": "correct_app_key",
            "app_secret": "correct_app_secret",
            "phone": "error_phone",
            "password": "correct_password",
        },
    )

    # Move to selecting a house
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"
    snapshot.assert_match(result2)
