"""Test the Rhasspy config flow."""
from unittest.mock import patch

from spencerassistant import config_entries
from spencerassistant.components.rhasspy.const import DOMAIN
from spencerassistant.core import spencerAssistant
from spencerassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: spencerAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "spencerassistant.components.rhasspy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Rhasspy"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_entry(hass: spencerAssistant) -> None:
    """Test we only allow single entry."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
