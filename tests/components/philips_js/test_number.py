"""Tests for the Philips TV number entities."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from haphilipsjs import ConnectionFailure, PhilipsTV
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL_NO

from tests.common import MockConfigEntry, async_fire_time_changed

CONTRAST_NODE_ID = 2130968795
BLACK_LEVEL_NODE_ID = 2130968793
CONTRAST_ENTITY_ID = "number.philips_tv_contrast"
BLACK_LEVEL_ENTITY_ID = "number.philips_tv_black_level"


def _slider(node_id: int, context: str, maximum: int = 100) -> dict:
    return {
        "node_id": node_id,
        "type": "SLIDER_NODE",
        "context": context,
        "data": {"slider_data": {"min": 0, "max": maximum, "step_size": 1}},
    }


MOCK_SETTINGS = {
    "node": {
        "node_id": 1,
        "type": "PARENT_NODE",
        "context": "Setup_Menu",
        "data": {
            "nodes": [
                {
                    "node_id": 2,
                    "type": "PARENT_NODE",
                    "context": "picture",
                    "data": {
                        "nodes": [
                            _slider(CONTRAST_NODE_ID, "contrast"),
                            _slider(BLACK_LEVEL_NODE_ID, "brightness"),
                            {
                                "node_id": 3,
                                "type": "LIST_NODE",
                                "context": "picture_style",
                                "data": {"enums": []},
                            },
                        ]
                    },
                }
            ]
        },
    }
}


def _value(node_id: int, value: int, available: bool = True) -> dict:
    return {
        "Nodeid": node_id,
        "Controllable": True,
        "Available": available,
        "string_id": "string",
        "data": {"value": value},
    }


@pytest.fixture(autouse=True)
def mock_settings(mock_tv: PhilipsTV) -> None:
    """Provide the menu settings of the TV."""
    mock_tv.settings = MOCK_SETTINGS
    mock_tv.getMenuItemsSettingsCurrentValue.return_value = {
        CONTRAST_NODE_ID: _value(CONTRAST_NODE_ID, 100),
        BLACK_LEVEL_NODE_ID: _value(BLACK_LEVEL_NODE_ID, 50),
    }


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_tv")
async def test_entities_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the discovered sliders are created disabled."""
    await _setup(hass, mock_config_entry)

    entry = entity_registry.async_get(CONTRAST_ENTITY_ID)
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.unique_id == f"{MOCK_SERIAL_NO}_contrast"
    assert hass.states.get(CONTRAST_ENTITY_ID) is None
    assert entity_registry.async_get(BLACK_LEVEL_ENTITY_ID)
    # Only sliders found in the menu structure of the TV are created
    assert entity_registry.async_get("number.philips_tv_gamma") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_state_and_set_value(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reading and changing a slider."""
    await _setup(hass, mock_config_entry)

    state = hass.states.get(CONTRAST_ENTITY_ID)
    assert state
    assert state.state == "100"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 100
    assert state.attributes["step"] == 1

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CONTRAST_ENTITY_ID, ATTR_VALUE: 40},
        blocking=True,
    )

    mock_tv.postMenuItemsSettingsUpdateData.assert_awaited_once_with(
        {CONTRAST_NODE_ID: {"value": 40}}
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unavailable_setting(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a setting the TV reports as not available."""
    mock_tv.getMenuItemsSettingsCurrentValue.return_value = {
        CONTRAST_NODE_ID: _value(CONTRAST_NODE_ID, 100, available=False),
        BLACK_LEVEL_NODE_ID: _value(BLACK_LEVEL_NODE_ID, 50),
    }
    await _setup(hass, mock_config_entry)

    assert hass.states.get(CONTRAST_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(BLACK_LEVEL_ENTITY_ID).state == "50"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_menu_settings(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no entities are created for a TV without menu settings."""
    mock_tv.settings = None
    await _setup(hass, mock_config_entry)

    assert entity_registry.async_get(CONTRAST_ENTITY_ID) is None
    mock_tv.getMenuItemsSettingsCurrentValue.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities_added_when_tv_turns_on(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sliders are added once the menu structure becomes available."""
    mock_tv.settings = None
    await _setup(hass, mock_config_entry)
    assert hass.states.get(CONTRAST_ENTITY_ID) is None

    mock_tv.settings = MOCK_SETTINGS
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CONTRAST_ENTITY_ID))
    assert state.state == "100"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("on", "powerstate"),
    [(False, None), (True, "Standby")],
    ids=["unreachable", "standby"],
)
async def test_unavailable_when_tv_not_on(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    on: bool,
    powerstate: str | None,
) -> None:
    """Test the sliders are unavailable while the TV is not on."""
    mock_tv.on = on
    mock_tv.powerstate = powerstate
    await _setup(hass, mock_config_entry)

    assert hass.states.get(CONTRAST_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_connection_failure_fetching_values(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entities are still created if the TV fails to answer."""
    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = ConnectionFailure
    await _setup(hass, mock_config_entry)

    assert hass.states.get(CONTRAST_ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_values_returned_by_tv(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a TV answering without values does not break the update."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get(CONTRAST_ENTITY_ID).state == "100"

    mock_tv.getMenuItemsSettingsCurrentValue.side_effect = KeyError("values")
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONTRAST_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get("media_player.philips_tv").state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_values_not_fetched_in_standby(
    hass: HomeAssistant,
    mock_tv: PhilipsTV,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the menu values are not requested while the TV is in standby."""
    mock_tv.powerstate = "Standby"
    await _setup(hass, mock_config_entry)

    mock_tv.getMenuItemsSettingsCurrentValue.assert_not_called()
