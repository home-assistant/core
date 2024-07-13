"""Test the PoolSense config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.poolsense.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_poolsense_client: AsyncMock
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "test"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@test.com"
    assert result["data"] == {
        CONF_EMAIL: "test@test.com",
        CONF_PASSWORD: "test",
    }
    assert result["result"].unique_id == "test@test.com"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_poolsense_client: AsyncMock
) -> None:
    """Test we handle invalid credentials."""
    mock_poolsense_client.test_poolsense_credentials.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "test"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_poolsense_client.test_poolsense_credentials.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "test"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_poolsense_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can't add the same entry twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_EMAIL: "test@test.com", CONF_PASSWORD: "test"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
