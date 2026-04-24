"""Tests for the Novy Hood button platform."""

from __future__ import annotations

import pytest
from rf_protocols import RadioFrequencyCommand

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.novy_hood.commands import (
    NovyHoodLight,
    NovyHoodMinus,
    NovyHoodPlus,
    NovyHoodPower,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity

BUTTONS: list[tuple[str, type[RadioFrequencyCommand]]] = [
    ("button.novy_hood_plus", NovyHoodPlus),
    ("button.novy_hood_minus", NovyHoodMinus),
    ("button.novy_hood_light", NovyHoodLight),
    ("button.novy_hood_power", NovyHoodPower),
]


@pytest.mark.parametrize(("entity_id", "expected_cls"), BUTTONS)
async def test_press_sends_command(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
    entity_id: str,
    expected_cls: type[RadioFrequencyCommand],
) -> None:
    """Each command button sends its matching RF command once."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_rf_entity.send_command_calls) == 1
    assert isinstance(mock_rf_entity.send_command_calls[0].command, expected_cls)


async def test_all_buttons_are_config_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """All remote-command buttons are exposed as config entities."""
    for entity_id, _ in BUTTONS:
        entry = entity_registry.async_get(entity_id)
        assert entry is not None, entity_id
        assert entry.entity_category is EntityCategory.CONFIG, entity_id
