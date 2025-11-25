"""Tests for Entity Migration integration setup."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.components.entity_migration.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Test integration setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Verify the integration is loaded
    assert DOMAIN in hass.config.components

    # Verify the scan service is registered
    assert hass.services.has_service(DOMAIN, "scan")


async def test_service_scan_valid_entity(
    hass: HomeAssistant,
    init_integration: None,
    mock_all_helpers: dict,
) -> None:
    """Test scan service with a valid entity ID."""
    # Create a test entity state
    hass.states.async_set("sensor.test_entity", "on")

    result = await hass.services.async_call(
        DOMAIN,
        "scan",
        {"entity_id": "sensor.test_entity"},
        blocking=True,
        return_response=True,
    )

    assert result is not None
    assert result["source_entity_id"] == "sensor.test_entity"
    assert "references" in result
    assert "total_count" in result


async def test_service_scan_invalid_entity_format(
    hass: HomeAssistant,
    init_integration: None,
) -> None:
    """Test scan service with invalid entity ID format."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "scan",
            {"entity_id": "invalid_entity_id"},
            blocking=True,
            return_response=True,
        )
