"""Test the ZhongHong setup and YAML import."""

from typing import Any

import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.zhong_hong.const import (
    CONF_GATEWAY_ADDRESS,
    DEFAULT_GATEWAY_ADDRESS,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import ENTITY_ID, HOST, FakeGateway

from tests.common import MockConfigEntry

YAML_CONFIG = {CLIMATE_DOMAIN: {"platform": DOMAIN, CONF_HOST: HOST}}


async def test_setup_and_unload(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test the gateway is listening while the entry is loaded."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_gateway.start_listen_calls == 1
    assert hass.states.get(ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_gateway.stop_listen_calls == 1


@pytest.mark.parametrize(
    ("attribute", "value"),
    [("discovery_error", OSError), ("discovery_result", [])],
    ids=["discovery_fails", "no_devices_found"],
)
async def test_setup_retries_without_devices(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    attribute: str,
    value: Any,
) -> None:
    """Test setup is retried when discovery does not yield devices."""
    setattr(mock_gateway, attribute, value)

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_gateway.start_listen_calls == 0


async def test_setup_stops_listener_when_the_first_query_fails(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test the listener is stopped when the entry fails after it was started.

    The gateway takes one connection at a time, so a socket left behind by a
    failed setup is what the retry would then be refused by.
    """
    mock_gateway.query_all_status_result = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_gateway.start_listen_calls == 1
    assert mock_gateway.stop_listen_calls == 1


async def test_setup_asks_for_the_state_of_every_device(
    hass: HomeAssistant, mock_gateway: FakeGateway, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entities have state without waiting for someone to touch a unit.

    The gateway reports a unit when it changes and not before, so the first
    state of each one has to be asked for.
    """
    await setup_integration(hass, mock_config_entry)

    assert mock_gateway.query_all_status_calls == 1
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_yaml_import(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a YAML configuration is imported into a config entry."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        CONF_HOST: HOST,
        CONF_PORT: DEFAULT_PORT,
        CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
    }
    assert hass.states.get(ENTITY_ID) is not None

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an already imported YAML configuration still asks to be removed.

    The import aborts here as well, but on an entry that already holds this
    configuration, so the YAML has served its purpose and can go.
    """
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_already_configured"
    )


@pytest.mark.parametrize(
    ("attribute", "value", "reason"),
    [
        ("discovery_error", OSError, "cannot_connect"),
        ("discovery_result", [], "no_devices_found"),
    ],
    ids=["cannot_connect", "no_devices_found"],
)
async def test_yaml_import_with_an_unreachable_gateway(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    issue_registry: ir.IssueRegistry,
    attribute: str,
    value: Any,
    reason: str,
) -> None:
    """Test a gateway that does not answer is reported instead of imported.

    The YAML can describe a gateway that has since been replaced or taken
    away, and a configuration entry that never works tells the user less than
    being shown which part of it no longer holds.

    Only the failure is reported. The notice that the YAML has been imported
    asks for it to be removed, which for a configuration that never made it
    into an entry would leave the integration with nothing at all.
    """
    setattr(mock_gateway, attribute, value)

    assert await async_setup_component(hass, CLIMATE_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_unique_ids_are_migrated_off_the_address(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity keeps its entity ID when its unique ID is replaced.

    The YAML platform identified an air conditioner by its address alone. The
    entity ID is what the history is recorded against, so it has to survive.
    """
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        CLIMATE_DOMAIN,
        DOMAIN,
        "zhong_hong_hvac_1_1",
        suggested_object_id="ac_1_1",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{mock_config_entry.entry_id}_1_1"


async def test_two_gateways_with_the_same_address(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an air conditioner at the same address on two gateways.

    `(1, 1)` is the first address on any bus, so two gateways having one is
    the ordinary case rather than a corner one. Identified by address alone
    both entities collided and Home Assistant added only the first.
    """
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="5.6.7.8",
        data={
            CONF_HOST: "5.6.7.8",
            CONF_PORT: DEFAULT_PORT,
            CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
        },
    )

    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, other_entry)

    assert other_entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 2


async def test_the_old_unique_id_is_left_with_its_owner(
    hass: HomeAssistant,
    mock_gateway: FakeGateway,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity another gateway owns is not taken over.

    Both gateways can have an air conditioner at `(1, 1)`, but only one of
    them owns the entity left behind under the old identifier. The owner
    moves it itself when it sets up; while it is not running, nobody else
    may, or that gateway's history would end up on this one.
    """
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        disabled_by=ConfigEntryDisabler.USER,
        data={
            CONF_HOST: "5.6.7.8",
            CONF_PORT: DEFAULT_PORT,
            CONF_GATEWAY_ADDRESS: DEFAULT_GATEWAY_ADDRESS,
        },
    )
    other_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        CLIMATE_DOMAIN,
        DOMAIN,
        "zhong_hong_hvac_1_1",
        config_entry=other_entry,
        suggested_object_id="ac_1_1",
    )

    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == "zhong_hong_hvac_1_1"
    assert entity_entry.config_entry_id == other_entry.entry_id
