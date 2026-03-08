"""Test the huum config flow."""

from unittest.mock import AsyncMock, patch

from huum.exceptions import Forbidden
import pytest

from homeassistant import config_entries
from homeassistant.components.huum.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USERNAME = "huum@sauna.org"
TEST_PASSWORD = "ukuuku"


async def test_form(
    hass: HomeAssistant, mock_huum: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USERNAME
    assert result2["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_signup_flow_already_set_up(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that we handle already existing entities with same id."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.ABORT


@pytest.mark.parametrize(
    (
        "raises",
        "error_base",
    ),
    [
        (Exception, "unknown"),
        (Forbidden, "invalid_auth"),
    ],
)
async def test_huum_errors(
    hass: HomeAssistant,
    mock_huum: AsyncMock,
    mock_setup_entry: AsyncMock,
    raises: Exception,
    error_base: str,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.huum.config_flow.Huum.status",
        side_effect=raises,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error_base}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
