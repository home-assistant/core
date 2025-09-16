"""Tests for the Stookwijzer services."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stookwijzer.const import DOMAIN, SERVICE_GET_FORECAST
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_service_get_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Stookwijzer forecast service."""

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_FORECAST,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )


@pytest.mark.usefixtures("init_integration")
async def test_service_entry_not_loaded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when entry is not loaded."""
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECAST,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id},
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_service_integration_not_found(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when integration not in registry."""
    with pytest.raises(
        ServiceValidationError, match='Integration "stookwijzer" not found in registry'
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_FORECAST,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"},
            blocking=True,
            return_response=True,
        )
