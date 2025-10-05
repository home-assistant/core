"""Test the Sequence config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.getsequence.api import SequenceConnectionError
from homeassistant.components.getsequence.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
            {
                "access_token": "test_token",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


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
