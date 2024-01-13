"""The tests for Netatmo switch."""
from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from .common import selected_platforms, snapshot_platform_entities

from tests.common import MockConfigEntry


async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.SWITCH,
        entity_registry,
        snapshot,
    )


async def test_switch_setup_and_services(
    hass: HomeAssistant, config_entry: MockConfigEntry, netatmo_auth: AsyncMock
) -> None:
    """Test setup and services."""
    with selected_platforms([Platform.SWITCH]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

    switch_entity = "switch.prise"

    assert hass.states.get(switch_entity).state == "on"

    # Test turning switch off
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: switch_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": "12:34:56:80:00:12:ac:f2",
                        "on": False,
                        "bridge": "12:34:56:80:60:40",
                    }
                ]
            }
        )

    # Test turning switch on
    with patch("pyatmo.home.Home.async_set_state") as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: switch_entity},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once_with(
            {
                "modules": [
                    {
                        "id": "12:34:56:80:00:12:ac:f2",
                        "on": True,
                        "bridge": "12:34:56:80:60:40",
                    }
                ]
            }
        )
