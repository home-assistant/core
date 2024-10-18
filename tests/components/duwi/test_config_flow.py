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


@pytest.mark.usefixtures("mock_duwi_login_user", "mock_duwi_fetch_house_info_error")
async def test_fetch_house_info_error(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow when fetch_house_info fails."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "app_key": "correct_app_key",
            "app_secret": "correct_app_secret",
            "phone": "correct_phone",
            "password": "correct_password",
        },
    )

    # Assert fetch_house_info error is caught
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "fetch_house_info_error"}
    snapshot.assert_match(result2)


@pytest.mark.usefixtures("mock_duwi_login_user", "mock_duwi_no_houses_found")
async def test_auth_success_but_no_houses_found(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow when authentication succeeds but no houses are found."""

    # Initialize the configuration flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Simulate user input with correct credentials
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "app_key": "correct_app_key",
            "app_secret": "correct_app_secret",
            "phone": "correct_phone",
            "password": "correct_password",
        },
    )

    # Check that the form is returned with the correct error when no houses are found
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "select_house"
    snapshot.assert_match(result2)


@pytest.mark.usefixtures("mock_duwi_login_invalid_auth")
async def test_invalid_auth_error(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow with invalid authentication."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "app_key": "correct_app_key",
            "app_secret": "correct_app_secret",
            "phone": "correct_phone",
            "password": "wrong_password",
        },
    )

    # Assert invalid authentication error
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "invalid_auth"}
    snapshot.assert_match(result2)


@pytest.mark.usefixtures("mock_duwi_login_sys_error")
async def test_invalid_sys_error(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the configuration flow with invalid authentication."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "app_key": "correct_app_key",
            "app_secret": "correct_app_secret",
            "phone": "correct_phone",
            "password": "wrong_password",
        },
    )

    # Assert invalid authentication error
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "sys_error"}
    snapshot.assert_match(result2)
