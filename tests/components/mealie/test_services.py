"""Tests for the Mealie services."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.mealie.const import ATTR_CONFIG_ENTRY_ID, DOMAIN
from homeassistant.components.mealie.services import SERVICE_GET_MEALPLAN_TODAY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


async def test_service_mealplan_today(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_mealplan_today service."""
    mock_config_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN_TODAY,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN_TODAY,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"},
            blocking=True,
            return_response=True,
        )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN_TODAY,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert mock_mealie_client.get_mealplan_today.called
    assert response == snapshot
