"""Define tests for the The Things Network init."""

import pytest
from ttn_client import TTNAuthError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import DOMAIN


async def test_error_configuration(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issue is logged when deprecated configuration is used."""
    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"app_id": "123", "access_key": "42"}}
    )
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "manual_migration")


@pytest.mark.parametrize(("exception_class"), [TTNAuthError, Exception])
async def test_init_exceptions(
    hass: HomeAssistant, mock_ttnclient, exception_class, mock_config_entry
) -> None:
    """Test TTN Exceptions."""

    mock_ttnclient.return_value.fetch_data.side_effect = exception_class
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
