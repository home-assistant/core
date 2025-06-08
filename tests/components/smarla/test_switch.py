"""Test switch platform for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, update_property_listeners

from tests.common import MockConfigEntry, snapshot_platform

SWITCH_ENTITIES = [
    {
        "entity_id": "switch.smarla",
        "service": "babywiege",
        "property": "swing_active",
    },
    {
        "entity_id": "switch.smarla_smart_mode",
        "service": "babywiege",
        "property": "smart_mode",
    },
]


@pytest.mark.usefixtures("mock_federwiege")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Smarla entities."""
    with (
        patch("homeassistant.components.smarla.PLATFORMS", [Platform.SWITCH]),
    ):
        assert await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("service", "parameter"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
@pytest.mark.parametrize("entity_info", SWITCH_ENTITIES)
async def test_switch_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    entity_info: dict[str, str],
    service: str,
    parameter: bool,
) -> None:
    """Test Smarla Switch on/off behavior."""
    assert await setup_integration(hass, mock_config_entry)

    mock_switch_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    # Turn on
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_switch_property.set.assert_called_once_with(parameter)


@pytest.mark.parametrize("entity_info", SWITCH_ENTITIES)
async def test_switch_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_federwiege: MagicMock,
    entity_info: dict[str, str],
) -> None:
    """Test Smarla Switch callback."""
    assert await setup_integration(hass, mock_config_entry)

    mock_switch_property = mock_federwiege.get_property(
        entity_info["service"], entity_info["property"]
    )

    entity_id = entity_info["entity_id"]

    assert hass.states.get(entity_id).state == STATE_OFF

    mock_switch_property.get.return_value = True

    await update_property_listeners(mock_switch_property)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
