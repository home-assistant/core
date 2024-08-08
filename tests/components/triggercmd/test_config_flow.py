"""Define tests for the triggercmd config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.triggercmd.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

invalid_token_with_length_100_or_more = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjEyMzQ1Njc4OTBxd2VydHl1aW9wYXNkZiIsImlhdCI6MTcxOTg4MTU4M30.E4T2S4RQfuI2ww74sUkkT-wyTGrV5_VDkgUdae5yo4E"


@pytest.fixture
def mock_hub():
    """Create a mock hub."""
    with patch("homeassistant.components.triggercmd.hub.Hub") as mock_hub_class:
        mock_hub_instance = mock_hub_class.return_value
        mock_hub_instance.test_connection = MagicMock(return_value=True)
        yield mock_hub_instance


async def test_config_flow_user_invalid_token(
    hass: HomeAssistant,
) -> None:
    """Test the initial step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.triggercmd.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": invalid_token_with_length_100_or_more},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
