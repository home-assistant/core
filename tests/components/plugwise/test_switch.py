"""Tests for the Plugwise switch integration."""
from unittest.mock import MagicMock

from plugwise.exceptions import PlugwiseException
import pytest

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_adam_climate_switch_entities(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related switch entities."""
    state = hass.states.get("switch.cv_pomp_relay")
    assert state
    assert state.state == "on"

    state = hass.states.get("switch.fibaro_hc2_relay")
    assert state
    assert state.state == "on"


async def test_adam_climate_switch_negative_testing(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test exceptions of climate related switch entities."""
    mock_smile_adam.set_switch_state.side_effect = PlugwiseException

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.cv_pomp_relay"},
            blocking=True,
        )

    assert mock_smile_adam.set_switch_state.call_count == 1
    mock_smile_adam.set_switch_state.assert_called_with(
        "78d1126fc4c743db81b61c20e88342a7", None, "relay", "off"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.fibaro_hc2_relay"},
            blocking=True,
        )

    assert mock_smile_adam.set_switch_state.call_count == 2
    mock_smile_adam.set_switch_state.assert_called_with(
        "a28f588dc4a049a483fd03a30361ad3a", None, "relay", "on"
    )


async def test_adam_climate_switch_changes(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of climate related switch entities."""
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.cv_pomp_relay"},
        blocking=True,
    )

    assert mock_smile_adam.set_switch_state.call_count == 1
    mock_smile_adam.set_switch_state.assert_called_with(
        "78d1126fc4c743db81b61c20e88342a7", None, "relay", "off"
    )

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.fibaro_hc2_relay"},
        blocking=True,
    )

    assert mock_smile_adam.set_switch_state.call_count == 2
    mock_smile_adam.set_switch_state.assert_called_with(
        "a28f588dc4a049a483fd03a30361ad3a", None, "relay", "off"
    )

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fibaro_hc2_relay"},
        blocking=True,
    )

    assert mock_smile_adam.set_switch_state.call_count == 3
    mock_smile_adam.set_switch_state.assert_called_with(
        "a28f588dc4a049a483fd03a30361ad3a", None, "relay", "on"
    )


async def test_stretch_switch_entities(
    hass: HomeAssistant, mock_stretch: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related switch entities."""
    state = hass.states.get("switch.koelkast_92c4a_relay")
    assert state
    assert state.state == "on"

    state = hass.states.get("switch.droger_52559_relay")
    assert state
    assert state.state == "on"


async def test_stretch_switch_changes(
    hass: HomeAssistant, mock_stretch: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of power related switch entities."""
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.koelkast_92c4a_relay"},
        blocking=True,
    )
    assert mock_stretch.set_switch_state.call_count == 1
    mock_stretch.set_switch_state.assert_called_with(
        "e1c884e7dede431dadee09506ec4f859", None, "relay", "off"
    )

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.droger_52559_relay"},
        blocking=True,
    )
    assert mock_stretch.set_switch_state.call_count == 2
    mock_stretch.set_switch_state.assert_called_with(
        "cfe95cf3de1948c0b8955125bf754614", None, "relay", "off"
    )

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.droger_52559_relay"},
        blocking=True,
    )
    assert mock_stretch.set_switch_state.call_count == 3
    mock_stretch.set_switch_state.assert_called_with(
        "cfe95cf3de1948c0b8955125bf754614", None, "relay", "on"
    )


async def test_unique_id_migration_plug_relay(
    hass: HomeAssistant, mock_smile_adam: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test unique ID migration of -plugs to -relay."""
    mock_config_entry.add_to_hass(hass)

    registry = er.async_get(hass)
    # Entry to migrate
    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "21f2b542c49845e6bb416884c55778d6-plug",
        config_entry=mock_config_entry,
        suggested_object_id="playstation_smart_plug",
        disabled_by=None,
    )
    # Entry not needing migration
    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "675416a629f343c495449970e2ca37b5-relay",
        config_entry=mock_config_entry,
        suggested_object_id="ziggo_modem",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.playstation_smart_plug") is not None
    assert hass.states.get("switch.ziggo_modem") is not None

    entity_entry = registry.async_get("switch.playstation_smart_plug")
    assert entity_entry
    assert entity_entry.unique_id == "21f2b542c49845e6bb416884c55778d6-relay"

    entity_entry = registry.async_get("switch.ziggo_modem")
    assert entity_entry
    assert entity_entry.unique_id == "675416a629f343c495449970e2ca37b5-relay"
