"""Test the eurotronic_cometblue number platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FIXTURE_MAC
from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform


def _number_entity_id(entity_registry: er.EntityRegistry, key: str) -> str:
    """Resolve a number entity id by unique id."""
    unique_id = f"{FIXTURE_MAC}-{key}"
    entity_id = entity_registry.async_get_entity_id(
        "number", "eurotronic_cometblue", unique_id
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_number_disabled_by_default_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabled-by-default number entities are not available."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    for key in ("offset", "window_open_delay"):
        entity_id = _number_entity_id(entity_registry, key)

        assert (entry := entity_registry.async_get(entity_id))
        assert entry.disabled_by is not None
        assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("entity_id", "value", "default_value"),
    [
        ("number.comet_blue_aa_bb_cc_dd_ee_ff_target_temperature_low", 18.5, 17.0),
        ("number.comet_blue_aa_bb_cc_dd_ee_ff_target_temperature_high", 23.0, 21.0),
    ],
)
async def test_set_number_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: float,
    default_value: float,
) -> None:
    """Test setting writable number entities."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.NUMBER])

    # check the default values
    assert (state := hass.states.get(entity_id))
    assert float(state.state) == default_value

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    assert (state := hass.states.get(entity_id))
    assert float(state.state) == value
