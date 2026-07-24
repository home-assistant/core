"""Test the Nina services."""

from unittest.mock import AsyncMock

from pynina import Warning
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nina.const import DOMAIN, SERVICE_GET_DETAILS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_platform, setup_single_platform

from tests.common import MockConfigEntry


async def test_service_registration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nina_class: AsyncMock
) -> None:
    """Test the NINA services be registered."""
    await setup_single_platform(hass, mock_config_entry, None, mock_nina_class, [])

    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 1
    assert SERVICE_GET_DETAILS in services


async def test_service_get_details(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get details service."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    target_entity_id = "binary_sensor.aach_warning_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DETAILS,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )
    assert result == snapshot


async def test_service_get_details_no_warning(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nina_class: AsyncMock
) -> None:
    """Test the get details service when no warning is present."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, [])

    target_entity_id = "binary_sensor.aach_warning_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DETAILS,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert result[target_entity_id] is None
