"""Test abstract template entity."""

from typing import Any

import pytest

from homeassistant.components.template import entity as abstract_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import ConfigurationStyle
from .test_switch import (
    TEST_ENTITY_ID as SWITCH_ENTITY_ID,
    TEST_OBJECT_ID,
    setup_switch_config,
)

from tests.common import MockConfigEntry


async def test_template_entity_not_implemented(hass: HomeAssistant) -> None:
    """Test abstract template entity raises not implemented error."""

    with pytest.raises(TypeError):
        _ = abstract_entity.AbstractTemplateEntity(hass, {})


async def setup_switch(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do the setup of all template switch configuration styles."""
    if style == ConfigurationStyle.LEGACY:
        config = {TEST_OBJECT_ID: config}
    else:
        config = {"name": TEST_OBJECT_ID, **config}

    await setup_switch_config(hass, 1, style, config)


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_device_actions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that device actions work for template entities."""
    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entity_entry = entity_registry.async_get_or_create(
        "fake_integration", "test", "5678", device_id=device_entry.id
    )

    await setup_switch(
        hass,
        style,
        {
            "turn_on": {
                "domain": "fake_integration",
                "type": "turn_on",
                "device_id": device_entry.id,
                "entity_id": entity_entry.id,
                "metadata": {"secondary": False},
            },
            "turn_off": {
                "domain": "fake_integration",
                "type": "turn_off",
                "device_id": device_entry.id,
                "entity_id": entity_entry.id,
                "metadata": {"secondary": False},
            },
        },
    )

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
    )

    assert (
        "not a valid value for dictionary value @ data['entity_id']" not in caplog.text
    )
