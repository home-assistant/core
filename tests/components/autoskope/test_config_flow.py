"""Test the Autoskope config flow."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.autoskope.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.autoskope.const import DEFAULT_HOST, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    CONF_USERNAME: "test-user",
    CONF_PASSWORD: "test-pass",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # Patch validate_input for the success case
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={"title": "Autoskope Test"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Autoskope Test"
    assert result2["data"] == {
        **MOCK_CONFIG,
        CONF_HOST: DEFAULT_HOST,  # Ensure host is added correctly
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Patch validate_input to raise InvalidAuth
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi.authenticate",
        side_effect=CannotConnect,  # Simulate connection error
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "https://test.host",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        "base": "cannot_connect"
    }  # Check for correct error key


async def test_reauth_flow(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Test the re-authentication configuration flow."""
    # ... existing setup ...
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{MOCK_CONFIG[CONF_USERNAME]}@{DEFAULT_HOST}",  # Use correct unique_id format
        data={**MOCK_CONFIG, CONF_HOST: DEFAULT_HOST, CONF_PASSWORD: "old-password"},
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Patch validate_input for the reauth success case
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={
            "title": "Reauth Success"
        },  # Return value doesn't matter much here
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_auth_error(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Test the re-authentication configuration flow with authentication error."""
    # ... existing setup ...
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{MOCK_CONFIG[CONF_USERNAME]}@{DEFAULT_HOST}",  # Use correct unique_id format
        data={**MOCK_CONFIG, CONF_HOST: DEFAULT_HOST, CONF_PASSWORD: "old-password"},
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Patch validate_input to raise InvalidAuth
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"]["base"] == "invalid_auth"


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauth flow with CannotConnect."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    # Mock validate_input to raise CannotConnect
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "any_password"},  # Password doesn't matter here
        )
        await hass.async_block_till_done()

    # Should show form again with cannot_connect error
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Patch validate_input to raise a generic Exception
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=Exception("Unknown error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )

    assert result2["type"] == FlowResultType.FORM
    # The generic exception in async_step_user catches this
    assert result2["errors"] == {"base": "unknown"}


async def test_host_validation(hass: HomeAssistant) -> None:
    """Test validation of host parameter."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    custom_host = "https://custom.autoskope.com"
    # Submit step user with custom host
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={"title": "Autoskope Test Custom Host"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **MOCK_CONFIG,
                CONF_HOST: custom_host,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == custom_host


async def test_form_multiple_entries(hass: HomeAssistant) -> None:
    """Test we handle multiple entries."""
    # Create a config entry first
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={"title": "Autoskope Test 1"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_USERNAME] == MOCK_CONFIG[CONF_USERNAME]

    # Try creating another entry with different credentials
    another_config = {
        CONF_USERNAME: "another-user",
        CONF_PASSWORD: "another-password",
        CONF_HOST: "https://another.host.com",  # Use a different host
    }
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={"title": "Autoskope Test 2"},
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"], another_config
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Autoskope Test 2"
    assert result4["data"][CONF_USERNAME] == another_config[CONF_USERNAME]
    assert result4["data"][CONF_HOST] == another_config[CONF_HOST]


async def test_form_user_initiated_retry(hass: HomeAssistant) -> None:
    """Test handling of a user-initiated retry after an error."""
    # First attempt with an error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_CONFIG
        )

    # Should return an error
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    # Try again with successful validation
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={"title": "Autoskope Retry Success"},
    ):
        # Use the same flow_id (result2["flow_id"]) for the retry
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], MOCK_CONFIG
        )
        await hass.async_block_till_done()

    # Should create entry successfully
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Autoskope Retry Success"


async def test_user_form_already_configured(hass: HomeAssistant) -> None:
    """Test user config flow when an entry is already configured."""
    # Create a MockConfigEntry representing the existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{MOCK_CONFIG[CONF_USERNAME]}@{DEFAULT_HOST}",  # Correct unique_id format
        data={**MOCK_CONFIG, CONF_HOST: DEFAULT_HOST},
        title="Existing Autoskope",
    )
    existing_entry.add_to_hass(hass)

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Attempt to configure using data that generates the same unique_id
    # (Username is the same, host defaults to DEFAULT_HOST)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,  # This implies default host
    )
    await hass.async_block_till_done()

    # Should abort because entry already exists
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test the reauth flow success path."""
    # Create a specific MockConfigEntry for this test with the correct unique_id
    entry_data = {**MOCK_CONFIG, CONF_HOST: DEFAULT_HOST}
    entry_unique_id = f"{entry_data[CONF_USERNAME]}@{entry_data[CONF_HOST]}"
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=entry_unique_id,
        data=entry_data,
        title="Autoskope Reauth Test",
    )
    entry.add_to_hass(hass)

    # Initiate reauth flow using the specific entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,  # Use the specific entry's ID
        },
        data=entry.data,  # Use the specific entry's data
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        "name": entry.title,  # Use the specific entry's title
        "username": entry.data[CONF_USERNAME],  # Use the specific entry's username
    }

    # Mock validate_input to return success
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        return_value={"title": "Autoskope"},  # Return value doesn't matter much
    ) as mock_validate:
        # Provide updated credentials
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new_password"},
        )
        await hass.async_block_till_done()

    # Check validation was called with merged data
    mock_validate.assert_called_once_with(
        hass, {**entry.data, CONF_PASSWORD: "new_password"}
    )

    # Check the specific entry was updated
    assert entry.data[CONF_PASSWORD] == "new_password"

    # Check flow finished
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauth flow with InvalidAuth."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    # Mock validate_input to raise InvalidAuth
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "wrong_password"},
        )
        await hass.async_block_till_done()

    # Should show form again with invalid_auth error
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_generic_exception(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauth flow with a generic Exception."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )

    # Mock validate_input to raise Exception
    with patch(
        "homeassistant.components.autoskope.config_flow.validate_input",
        side_effect=Exception("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "any_password"},
        )
        await hass.async_block_till_done()

    # Should show form again with unknown error
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "unknown"}


# --- Tests specifically for validate_input ---


async def test_validate_input_success(hass: HomeAssistant) -> None:
    """Test validate_input success path."""
    mock_api = AsyncMock()
    mock_api.authenticate = AsyncMock(return_value=True)  # Simulate successful auth

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi",
        return_value=mock_api,
    ) as mock_api_init:
        result = await validate_input(hass, MOCK_CONFIG)

    # Check API was initialized and authenticate called
    mock_api_init.assert_called_once_with(
        host=DEFAULT_HOST,  # Check default host is used
        username=MOCK_CONFIG[CONF_USERNAME],
        password=MOCK_CONFIG[CONF_PASSWORD],
        hass=hass,
    )
    mock_api.authenticate.assert_awaited_once()
    # Check result contains the expected title format
    assert result == {"title": f"Autoskope {MOCK_CONFIG[CONF_USERNAME]}"}


async def test_validate_input_invalid_auth(hass: HomeAssistant) -> None:
    """Test validate_input raises InvalidAuth."""
    mock_api = AsyncMock()
    mock_api.authenticate = AsyncMock(side_effect=InvalidAuth)  # Simulate auth failure

    with (
        patch(
            "homeassistant.components.autoskope.config_flow.AutoskopeApi",
            return_value=mock_api,
        ),
        pytest.raises(InvalidAuth),
    ):  # Expect InvalidAuth to be raised
        await validate_input(hass, MOCK_CONFIG)


async def test_validate_input_cannot_connect(hass: HomeAssistant) -> None:
    """Test validate_input raises CannotConnect."""
    mock_api = AsyncMock()
    mock_api.authenticate = AsyncMock(
        side_effect=CannotConnect
    )  # Simulate connection error

    with (
        patch(
            "homeassistant.components.autoskope.config_flow.AutoskopeApi",
            return_value=mock_api,
        ),
        pytest.raises(CannotConnect),
    ):  # Expect CannotConnect
        await validate_input(hass, MOCK_CONFIG)


async def test_validate_input_home_assistant_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test validate_input raises HomeAssistantError and logs."""
    mock_api = AsyncMock()
    error_message = "API Error during validation test"
    mock_api.authenticate = AsyncMock(side_effect=HomeAssistantError(error_message))

    # Set log level before the context manager
    caplog.set_level(logging.ERROR)

    with (
        patch(
            "homeassistant.components.autoskope.config_flow.AutoskopeApi",
            return_value=mock_api,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await validate_input(hass, MOCK_CONFIG)

    # Check that the specific error was logged
    # Correct the expected log message
    assert "Unexpected error during validation" in caplog.text
    assert error_message in caplog.text


async def test_validate_input_generic_exception(hass: HomeAssistant) -> None:
    """Test validate_input raises HomeAssistantError for generic exceptions."""
    mock_api = AsyncMock()
    mock_api.authenticate = AsyncMock(
        side_effect=Exception("Generic Error")
    )  # Simulate other error

    with (
        patch(
            "homeassistant.components.autoskope.config_flow.AutoskopeApi",
            return_value=mock_api,
        ),
        pytest.raises(HomeAssistantError),
    ):  # Expect it to be wrapped in HomeAssistantError
        await validate_input(hass, MOCK_CONFIG)
