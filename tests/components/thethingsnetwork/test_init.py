"""Define tests for the The Things Network init."""

import pytest
from ttn_client import TTNAuthError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import (
    APP_ID,
    CONFIG_ENTRY,
    DATA_UPDATE,
    DEVICE_FIELD,
    DEVICE_FIELD_2,
    DEVICE_ID,
    DEVICE_ID_2,
    DOMAIN,
)


async def test_normal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_TTNClient_coordinator,
) -> None:
    """Test a working configuratioms."""
    CONFIG_ENTRY.add_to_hass(hass)
    assert await hass.config_entries.async_setup(CONFIG_ENTRY.entry_id)

    await hass.async_block_till_done()

    # Check devices
    assert (
        device_registry.async_get_device(identifiers={(APP_ID, DEVICE_ID)}).name
        == DEVICE_ID
    )

    # Check entities
    assert entity_registry.async_get(f"sensor.{DEVICE_ID}_{DEVICE_FIELD}")

    # Test reaction to options update
    hass.config_entries.async_update_entry(
        CONFIG_ENTRY, data=CONFIG_ENTRY.data, options={"dummy": "new_value"}
    )

    assert not entity_registry.async_get(f"sensor.{DEVICE_ID_2}_{DEVICE_FIELD}")
    push_callback = mock_TTNClient_coordinator.call_args.kwargs["push_callback"]
    await push_callback(DATA_UPDATE)
    assert entity_registry.async_get(f"sensor.{DEVICE_ID_2}_{DEVICE_FIELD_2}")


@pytest.mark.parametrize(("exceptionClass"), [TTNAuthError, Exception])
async def test_client_exceptions(
    hass: HomeAssistant, mock_TTNClient_coordinator, exceptionClass
) -> None:
    """Test TTN Exceptions."""

    mock_TTNClient_coordinator.return_value.fetch_data.side_effect = exceptionClass
    CONFIG_ENTRY.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(CONFIG_ENTRY.entry_id)


async def test_error_configuration(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issue is logged when deprecated configuration is used."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "manual_migration")
