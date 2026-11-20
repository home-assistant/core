"""Tests for Daikin Onecta platforms other than climate."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from unittest.mock import AsyncMock

from daikin_onecta.client import OnectaClient
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.daikin_onecta.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
)
from homeassistant.components.daikin_onecta.button import BUTTON_DESCRIPTIONS
from homeassistant.components.daikin_onecta.select import SELECT_DESCRIPTIONS
from homeassistant.components.daikin_onecta.sensor import SENSOR_DESCRIPTIONS
from homeassistant.components.daikin_onecta.switch import SWITCH_DESCRIPTIONS
from homeassistant.components.daikin_onecta.update import UPDATE_DESCRIPTIONS
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityStateAttribute,
    FanServiceArgument,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE as WATER_HEATER_SERVICE_SET_TEMPERATURE,
    WaterHeaterServiceArgument,
    WaterHeaterStateAttribute,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import _execute_typed_command
from .test_climate_snapshots import _async_setup_fixture


async def test_platform_entities_become_unavailable_after_failed_update(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Publish coordinator failure through entities loaded by the config entry."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    entity_ids = sorted(
        {entry.entity_id for entry in entries}
        & set(hass.states.async_entity_ids()) - {"button.daikin_onecta_account_refresh"}
    )
    assert entity_ids

    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    states = [hass.states.get(entity_id) for entity_id in entity_ids]
    assert all(
        state is not None and state.state == "unavailable" for state in states
    ), states


async def test_account_entities_are_not_duplicated_for_multiple_gateways(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Create one account refresh and rate-limit entity for all gateways."""
    hass.config_entries.async_update_entry(config_entry, unique_id="account-id")

    await _async_setup_fixture(hass, config_entry, "climate_floorheatingairflow")

    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    entries_by_unique_id = {entry.unique_id: entry for entry in entries}
    assert entries_by_unique_id["account-id_refresh"].domain == BUTTON_DOMAIN
    assert (
        entries_by_unique_id["account-id_rate_limit_remaining_day"].domain
        == SENSOR_DOMAIN
    )


@pytest.mark.parametrize(
    "descriptions",
    [
        BINARY_SENSOR_DESCRIPTIONS,
        BUTTON_DESCRIPTIONS,
        SELECT_DESCRIPTIONS,
        SENSOR_DESCRIPTIONS,
        SWITCH_DESCRIPTIONS,
        UPDATE_DESCRIPTIONS,
    ],
)
def test_entity_descriptions_have_translation_keys(descriptions: dict) -> None:
    """Every described entity has a translated name."""
    assert all(
        description.translation_key is not None for description in descriptions.values()
    )


@pytest.mark.parametrize(
    ("fixture", "domain", "service", "entity_id", "data", "attribute", "expected"),
    [
        (
            "altherma_boost",
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            "water_heater.altherma_domestic_hot_water_tank",
            {WaterHeaterServiceArgument.TEMPERATURE: 50},
            WaterHeaterStateAttribute.TARGET_TEMPERATURE,
            50,
        ),
        (
            "mc80z",
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            "fan.air_purifier",
            {FanServiceArgument.PRESET_MODE: "auto_fan"},
            FanEntityStateAttribute.PRESET_MODE,
            "auto_fan",
        ),
        (
            "mc80z",
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            "fan.air_purifier",
            {FanServiceArgument.PERCENTAGE: 100},
            FanEntityStateAttribute.PERCENTAGE,
            100,
        ),
    ],
)
async def test_command_cache_survives_model_replacement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fixture: str,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, str | int],
    attribute: str,
    expected: str | int,
) -> None:
    """Update the current model if polling replaces it while a command waits."""
    await _async_setup_fixture(hass, config_entry, fixture)
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.async_execute_command = execute

    async def replace_model(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        for device in coordinator.data.values():
            device.set_device_data(deepcopy(device.device))
        return await execute(command)

    coordinator.async_execute_command = AsyncMock(side_effect=replace_model)
    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[attribute] == expected
