"""Test the Lutron Caseta config flow."""
from asynctest import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.lutron_caseta import DOMAIN
import homeassistant.components.lutron_caseta.config_flow as CasetaConfigFlow

from tests.common import MockConfigEntry


async def test_bridge_import_flow(hass):
    """Test a bridge entry gets created and set up during the import flow."""

    mock_host = "1.1.1.1"

    await setup.async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": mock_host},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == CasetaConfigFlow.ENTRY_DEFAULT_TITLE
    assert result["data"] == {"host": mock_host}
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_bridge_import(hass):
    """Test that creating a bridge entry with a duplicate host errors."""

    mock_host = "1.1.1.1"
    mock_entry = MockConfigEntry(domain=DOMAIN, data={"host": mock_host})
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        # Mock entry added, try initializing flow with duplicate host
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"host": mock_host},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_ALREADY_CONFIGURED
    assert len(mock_setup_entry.mock_calls) == 0
