"""Tests for the EPH Controls Ember climate platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyephember2.pyephember2 import EphEmberError, ZoneMode
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    DOMAIN as CLIMATE_DOMAIN,
    ClimateService,
    ClimateServiceArgument,
    HVACAction,
    HVACMode,
)
from homeassistant.components.ephember.const import DOMAIN
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    TargetKey,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import MOCK_PASSWORD, MOCK_USER_ID, MOCK_USERNAME

YAML_CONFIG = {
    CLIMATE_DOMAIN: {
        "platform": DOMAIN,
        "username": MOCK_USERNAME,
        "password": MOCK_PASSWORD,
    }
}


@pytest.mark.usefixtures("init_integration")
async def test_climate_entities(hass: HomeAssistant) -> None:
    """Test zones are set up as climate entities."""

    state = hass.states.get("climate.radiators")
    assert state.state == HVACMode.HEAT
    assert state.attributes["current_temperature"] == 20.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    state = hass.states.get("climate.hot_water")
    assert state.state == HVACMode.OFF
    assert state.attributes["current_temperature"] == 25.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_and_mode(
    hass: HomeAssistant, mock_ember: MagicMock
) -> None:
    """Test changing target temperature and mode."""

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: "climate.radiators",
            ClimateServiceArgument.TEMPERATURE: 21.5,
        },
        blocking=True,
    )
    mock_ember.set_zone_target_temperature.assert_called_once_with("zone1", 21.5)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: "climate.radiators",
            ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    mock_ember.set_zone_mode.assert_called_once_with("zone1", ZoneMode.OFF)


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_when_cloud_unreachable(
    hass: HomeAssistant,
    mock_ember: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities become unavailable, log once, and recover."""

    mock_ember.get_zones.side_effect = RuntimeError("Host is unreachable")
    for _ in range(3):
        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("climate.radiators").state == STATE_UNAVAILABLE
    assert caplog.text.count("Unable to update Radiators") == 1

    mock_ember.get_zones.side_effect = None
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("climate.radiators").state == HVACMode.HEAT
    assert "Radiators is available again" in caplog.text


@pytest.mark.usefixtures("mock_ember")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the YAML configuration is imported and flagged as deprecated."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == MOCK_USER_ID
    assert entries[0].data == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
    }
    assert hass.states.get("climate.radiators").state == HVACMode.HEAT
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_ember")
async def test_yaml_import_already_imported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML for an account that is already set up is not imported again."""
    mock_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (EphEmberError("Host is unreachable"), "cannot_connect"),
        (RuntimeError("Unable to login."), "invalid_auth"),
        (ValueError("Unexpected"), "unknown"),
    ],
)
async def test_yaml_import_fails(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_ember: MagicMock,
    error: Exception,
    reason: str,
) -> None:
    """Test a repair issue explains why the YAML could not be imported."""
    mock_ember.messenging_credentials.side_effect = error
    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_ember")
async def test_yaml_import_keeps_existing_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test entities created by the YAML platform are adopted by the import."""
    entity_registry.async_get_or_create(
        CLIMATE_DOMAIN, DOMAIN, "zone1", suggested_object_id="my_radiators"
    )

    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entity = entity_registry.async_get("climate.my_radiators")
    assert entity.config_entry_id == entry.entry_id
    assert hass.states.get("climate.my_radiators").state == HVACMode.HEAT


async def test_live_update(
    hass: HomeAssistant, mock_ember: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test a live update from the cloud is shown straight away."""
    zone_updated = mock_ember.start_listening.call_args.args[0]

    radiators = mock_ember.get_zone("zone1")
    radiators["pointDataList"] = [
        {"pointIndex": 5, "value": "188"},
        {"pointIndex": 6, "value": "220"},
        {"pointIndex": 7, "value": "3"},
        {"pointIndex": 10, "value": "1"},
    ]
    # the library calls back from its listener thread
    await hass.async_add_executor_job(zone_updated, radiators)
    await hass.async_block_till_done()

    state = hass.states.get("climate.radiators")
    assert state.state == HVACMode.OFF
    assert state.attributes["current_temperature"] == 18.8
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
