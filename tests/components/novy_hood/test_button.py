"""Tests for the Novy Hood button platform."""

from __future__ import annotations

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.novy_hood.commands import NovyHoodPower
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from tests.common import MockConfigEntry
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity

ENTITY_ID = "button.novy_hood_power"


async def test_press_sends_power(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """Pressing the button sends the `power` RF command once."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert len(mock_rf_entity.send_command_calls) == 1
    assert isinstance(mock_rf_entity.send_command_calls[0].command, NovyHoodPower)


async def test_entity_category_is_config(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """The experimental power button is exposed as a config entity."""
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.entity_category is EntityCategory.CONFIG
