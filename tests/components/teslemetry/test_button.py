"""Test the Teslemetry button platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.teslemetry.const import (
    DOMAIN,
    LABS_CHARGE_ON_SOLAR_FEATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import assert_entities, setup_platform
from .const import COMMAND_OK


async def _async_enable_charge_on_solar_preview_feature(hass: HomeAssistant) -> None:
    """Enable the Teslemetry charge-on-solar preview feature."""
    assert await async_setup_component(hass, "labs", {})
    await async_update_preview_feature(hass, DOMAIN, LABS_CHARGE_ON_SOLAR_FEATURE, True)


def _get_button_entity_id_by_translation_key(
    entity_registry: er.EntityRegistry,
    entry_id: str,
    translation_key: str,
) -> str | None:
    """Return button entity_id for a translation key."""
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if (
            entity_entry.domain == "button"
            and entity_entry.translation_key == translation_key
        ):
            return entity_entry.entity_id
    return None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the button entities are correct."""

    entry = await setup_platform(hass, [Platform.BUTTON])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("name", "func"),
    [
        ("wake", "wake_up"),
        ("flash_lights", "flash_lights"),
        ("honk_horn", "honk_horn"),
        ("keyless_driving", "remote_start_drive"),
        ("play_fart", "remote_boombox"),
        ("homelink", "trigger_homelink"),
    ],
)
async def test_press(hass: HomeAssistant, name: str, func: str) -> None:
    """Test pressing the API buttons."""
    await setup_platform(hass, [Platform.BUTTON])

    with patch(
        f"tesla_fleet_api.teslemetry.Vehicle.{func}",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [f"button.test_{name}"]},
            blocking=True,
        )
        command.assert_called_once()


async def test_charge_on_solar_buttons_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test charge-on-solar buttons are disabled by default."""
    entry = await setup_platform(hass, [Platform.BUTTON])

    assert (
        _get_button_entity_id_by_translation_key(
            entity_registry, entry.entry_id, "enable_charge_on_solar"
        )
        is None
    )
    assert (
        _get_button_entity_id_by_translation_key(
            entity_registry, entry.entry_id, "disable_charge_on_solar"
        )
        is None
    )


async def test_charge_on_solar_buttons_enabled_by_labs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test charge-on-solar buttons appear when Labs feature is enabled."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    entry = await setup_platform(hass, [Platform.BUTTON])

    enable_entity_id = _get_button_entity_id_by_translation_key(
        entity_registry, entry.entry_id, "enable_charge_on_solar"
    )
    disable_entity_id = _get_button_entity_id_by_translation_key(
        entity_registry, entry.entry_id, "disable_charge_on_solar"
    )

    assert enable_entity_id is not None
    assert disable_entity_id is not None
    assert hass.states.get(enable_entity_id) is not None
    assert hass.states.get(disable_entity_id) is not None


@pytest.mark.parametrize(
    ("translation_key", "enabled"),
    [
        ("enable_charge_on_solar", True),
        ("disable_charge_on_solar", False),
    ],
)
async def test_press_charge_on_solar_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    translation_key: str,
    enabled: bool,
) -> None:
    """Test pressing charge-on-solar buttons calls the expected API."""
    await _async_enable_charge_on_solar_preview_feature(hass)
    entry = await setup_platform(hass, [Platform.BUTTON])

    entity_id = _get_button_entity_id_by_translation_key(
        entity_registry, entry.entry_id, translation_key
    )
    assert entity_id is not None

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.charge_on_solar",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        command.assert_called_once_with(enabled=enabled)
