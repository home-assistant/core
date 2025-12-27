"""Test the Sequence config flow."""

from unittest.mock import patch

from GetSequenceIoApiClient import (
    SequenceApiError,
    SequenceAuthError,
    SequenceConnectionError,
)

from homeassistant import config_entries
from homeassistant.components.getsequence.config_flow import SequenceOptionsFlow
from homeassistant.components.getsequence.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_options_flow_empty_accounts_error_branch(hass: HomeAssistant) -> None:
    """Test options flow error branch when fetching accounts fails and choices are empty."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=Exception,
    ):
        result = await hass.config_entries.options.async_init(mock_config.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_filters_none(hass: HomeAssistant) -> None:
    """Test options flow filters out 'none' from input and marks liability configured."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        return_value={
            "data": {
                "accounts": [
                    {"id": "1001", "name": "Credit Card", "type": "Account"},
                    {"id": "1002", "name": "Investment Account", "type": "Account"},
                ]
            }
        },
    ):
        result = await hass.config_entries.options.async_init(mock_config.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        # Input includes 'none' which should be filtered out
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "liability_accounts": ["1001", "none"],
                "investment_accounts": ["none", "1002"],
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    # 'none' should be filtered out
    assert result2["data"] == {
        "liability_accounts": ["1001"],
        "investment_accounts": ["1002"],
        "liability_configured": True,
    }


async def test_reauth_confirm_invalid_auth(hass: HomeAssistant) -> None:
    """Test reauth confirm step handles invalid_auth error."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "old_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=SequenceAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "bad_token"}
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test reauth confirm step handles cannot_connect error."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "old_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=SequenceConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "bad_token"}
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_confirm_unknown_error(hass: HomeAssistant) -> None:
    """Test reauth confirm step handles unknown error."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "old_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=SequenceApiError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "bad_token"}
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_confirm_description_placeholder(hass: HomeAssistant) -> None:
    """Test reauth confirm step includes description placeholders."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "old_token"},
        unique_id="test_unique_id",
        title="Test Account Title",
    )
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )
    # The form should include description_placeholders with account title
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert "description_placeholders" in result
    assert result["description_placeholders"]["account"] == mock_config.title


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
            return_value={
                "data": {
                    "accounts": [
                        {
                            "id": "5579244",
                            "name": "Test Pod",
                            "balance": {"amountInDollars": 1000.0, "error": None},
                            "type": "Pod",
                        }
                    ]
                }
            },
        ),
        patch(
            "homeassistant.components.getsequence.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "access_token": "test_token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sequence (1 pods)"
    assert result2["data"] == {
        "access_token": "test_token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"access_token": "test_token"},
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_sequence_auth_error(hass: HomeAssistant) -> None:
    """Test SequenceAuthError in config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=SequenceAuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"access_token": "test_token"},
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_sequence_api_error(hass: HomeAssistant) -> None:
    """Test SequenceApiError in config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=SequenceApiError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"access_token": "test_token"},
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_no_pods(hass: HomeAssistant) -> None:
    """Test config flow fallback when no pods exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch(
            "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
            return_value={"data": {"accounts": []}},
        ),
        patch(
            "homeassistant.components.getsequence.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"access_token": "test_token"},
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sequence"
    assert result2["data"] == {"access_token": "test_token"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=SequenceConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "access_token": "test_token",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "old_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        return_value={
            "data": {
                "accounts": [
                    {
                        "id": "5579244",
                        "name": "Test Pod",
                        "balance": {"amountInDollars": 1000.0, "error": None},
                        "type": "Pod",
                    }
                ]
            }
        },
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"access_token": "new_token"},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)

    # Mock the API call in options flow first, before starting the flow
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        return_value={
            "data": {
                "accounts": [
                    {
                        "id": "1001",
                        "name": "Credit Card",
                        "balance": {"amountInDollars": -500.0, "error": None},
                        "type": "Account",
                    },
                    {
                        "id": "1002",
                        "name": "Investment Account",
                        "balance": {"amountInDollars": 10000.0, "error": None},
                        "type": "Account",
                    },
                ]
            }
        },
    ):
        # Start options flow
        result = await hass.config_entries.options.async_init(mock_config.entry_id)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        # Configure liability and investment accounts
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "liability_accounts": ["1001"],
                "investment_accounts": ["1002"],
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "liability_accounts": ["1001"],
        "investment_accounts": ["1002"],
        "liability_configured": True,
    }


async def test_reauth_confirm_unexpected_exception(hass: HomeAssistant) -> None:
    """Test reauth confirm handles unexpected generic exceptions."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "old_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )
    with patch(
        "homeassistant.components.getsequence.config_flow.SequenceApiClient.async_get_accounts",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"access_token": "bad_token"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow_handles_non_list_values(hass: HomeAssistant) -> None:
    """Test options flow filters non-list entries via else branch."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={"access_token": "test_token"},
        unique_id="test_unique_id",
    )
    mock_config.add_to_hass(hass)

    # Provide at least one external account so the options form can be shown
    # Call the options flow handler directly to bypass the framework schema
    # validation so we can exercise the else branch for non-list values.
    # Build a minimal dummy 'self' with the attributes/methods the flow expects
    class DummyFlow:
        pass

    dummy = DummyFlow()
    dummy.hass = hass  # pylint: disable=attribute-defined-outside-init
    dummy.config_entry = mock_config  # pylint: disable=attribute-defined-outside-init

    def async_create_entry(title: str = "", data: dict | None = None):
        return {"type": "create_entry", "data": data or {}, "title": title}

    # Attach a simple create entry function to mimic the OptionsFlow behavior
    dummy.async_create_entry = async_create_entry  # pylint: disable=attribute-defined-outside-init

    # Call the unbound function with our dummy object to bypass framework checks
    result = await SequenceOptionsFlow.async_step_init(
        dummy, {"some_flag": "yes", "liability_accounts": ["1001"]}
    )

    assert result["type"] == "create_entry"
    assert result["data"]["some_flag"] == "yes"
    assert result["data"]["liability_configured"] is True
