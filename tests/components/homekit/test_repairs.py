"""Test the HomeKit repairs."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.homekit import HomeKit, async_remove_entry
from homeassistant.components.homekit.accessories import accessory_type_issue_id
from homeassistant.components.homekit.const import (
    CONF_ENTITY_CONFIG,
    DEFAULT_PORT,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODE_BRIDGE,
    ISSUE_ACCESSORY_TYPE_CANDIDATE,
    PERSIST_LOCK_DATA,
)
from homeassistant.components.homekit.util import get_aid_storage_filename_for_entry_id
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_EXCLUDE_ENTITY_GLOBS,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
    convert_filter,
)
from homeassistant.setup import async_setup_component

from .util import PATH_HOMEKIT

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def patch_source_ip() -> Generator[None]:
    """Patch homeassistant and pyhap functions for getting local address."""
    with patch("pyhap.util.get_local_address", return_value="10.10.10.10"):
        yield


ENTITY_ID = "climate.demo"
CAPABLE_ATTRS = {
    ATTR_SUPPORTED_FEATURES: (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    ),
    ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    ATTR_FAN_MODES: ["low", "high"],
}


INELIGIBLE_ATTRS = {
    ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
    ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
}
HUMIDITY_ATTRS = {
    **CAPABLE_ATTRS,
    ATTR_SUPPORTED_FEATURES: (
        CAPABLE_ATTRS[ATTR_SUPPORTED_FEATURES] | ClimateEntityFeature.TARGET_HUMIDITY
    ),
}


def _create_candidate_issue(
    hass: HomeAssistant, entry: MockConfigEntry, entity_id: str
) -> str:
    """Create a candidate issue like the bridge would and return its id."""
    issue_id = accessory_type_issue_id(entry.entry_id, entity_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ACCESSORY_TYPE_CANDIDATE,
        translation_placeholders={
            "entity": "demo",
            "entity_id": entity_id,
            "bridge": "mock_name",
        },
        data={"entry_id": entry.entry_id, "entity_id": entity_id},
    )
    return issue_id


async def _async_stop_bridge(homekit: HomeKit) -> None:
    """Stop the bridge and flush the delayed aid storage save.

    The flush lets a following start read the stored routing choices.
    """
    with patch("pyhap.accessory_driver.AccessoryDriver.async_stop"):
        await homekit.async_stop()
    assert homekit.aid_storage is not None
    await homekit.aid_storage.async_save()


async def _async_start_bridge(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    entity_config: dict[str, Any] | None = None,
    homekit_mode: str = HOMEKIT_MODE_BRIDGE,
    existing_pairing: bool = False,
) -> HomeKit:
    """Start a HomeKit instance exposing the demo climate entity."""
    hass.data.setdefault(PERSIST_LOCK_DATA, asyncio.Lock())
    entity_filter = convert_filter(
        {
            CONF_INCLUDE_DOMAINS: [],
            CONF_INCLUDE_ENTITIES: [ENTITY_ID],
            CONF_EXCLUDE_DOMAINS: [],
            CONF_EXCLUDE_ENTITIES: [],
            CONF_INCLUDE_ENTITY_GLOBS: [],
            CONF_EXCLUDE_ENTITY_GLOBS: [],
        }
    )
    homekit = HomeKit(
        hass=hass,
        name="mock_name",
        port=DEFAULT_PORT,
        ip_address=None,
        entity_filter=entity_filter,
        exclude_accessory_mode=False,
        entity_config=entity_config or {},
        homekit_mode=homekit_mode,
        advertise_ips=None,
        entry_id=entry.entry_id,
        entry_title=entry.title,
    )
    original_setup = HomeKit.setup

    def _setup(homekit: HomeKit, async_zeroconf_instance: Any, uuid: str) -> bool:
        """Run the real driver setup, faking persisted pairing state if asked."""
        loaded = original_setup(homekit, async_zeroconf_instance, uuid)
        return loaded or existing_pairing

    with (
        patch(f"{PATH_HOMEKIT}.async_show_setup_message"),
        patch("pyhap.accessory_driver.AccessoryDriver.async_start"),
        patch(f"{PATH_HOMEKIT}.HomeKit.setup", _setup),
    ):
        await homekit.async_start()
    await hass.async_block_till_done()
    return homekit


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_existing_entity_stays_thermostat_and_raises_issue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a previously bridged entity keeps the Thermostat and gets a repair."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass_storage[get_aid_storage_filename_for_entry_id(entry.entry_id)] = {
        "version": 1,
        "data": {"allocations": {ENTITY_ID: 1234567}},
    }
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    accessories = list(homekit.bridge.accessories.values())
    assert len(accessories) == 1
    assert type(accessories[0]).__name__ == "Thermostat"
    assert issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_new_entity_routes_to_heater_cooler_without_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a never bridged entity gets the HeaterCooler and no repair."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    accessories = list(homekit.bridge.accessories.values())
    assert len(accessories) == 1
    assert type(accessories[0]).__name__ == "HeaterCooler"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_failed_accessory_creation_is_not_recorded(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed accessory creation does not persist the auto routing."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    with patch(f"{PATH_HOMEKIT}.get_accessory", side_effect=ValueError):
        homekit = await _async_start_bridge(hass, entry)

    assert homekit.aid_storage is not None
    assert homekit.aid_storage.get_accessory_type(ENTITY_ID) is None
    # The aid allocation is rolled back so the entity is still new
    assert not homekit.aid_storage.allocations
    await _async_stop_bridge(homekit)

    # The next start treats the entity as never bridged and retries
    # the automatic choice
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "HeaterCooler"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_heater_cooler_choice_survives_restart(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the automatic HeaterCooler choice persists across restarts."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "HeaterCooler"
    await _async_stop_bridge(homekit)

    # The entity now has an aid allocation, so only the stored choice
    # keeps it on the HeaterCooler after a restart.
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "HeaterCooler"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_gained_humidity_setpoint_drops_stored_choice(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a stored HeaterCooler choice is dropped for a humidity setpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "HeaterCooler"
    await _async_stop_bridge(homekit)

    # The entity gains a humidity setpoint, which the HeaterCooler cannot
    # control, so the stored routing is dropped
    hass.states.async_set(
        ENTITY_ID,
        HVACMode.COOL,
        HUMIDITY_ATTRS,
    )
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "Thermostat"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    assert homekit.aid_storage is not None
    assert homekit.aid_storage.get_accessory_type(ENTITY_ID) is None
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_reload_accessory_resyncs_issue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test reloading an accessory keeps its repair issue in sync."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass_storage[get_aid_storage_filename_for_entry_id(entry.entry_id)] = {
        "version": 1,
        "data": {"allocations": {ENTITY_ID: 1234567}},
    }
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)
    issue_id = accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    # Losing the fan speeds makes the entity ineligible, so a reload
    # removes the stale issue
    hass.states.async_set(
        ENTITY_ID,
        HVACMode.COOL,
        INELIGIBLE_ATTRS,
    )
    await homekit.async_reload_accessories([ENTITY_ID])
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)

    # Regaining the capability recreates the issue on reload
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)
    await homekit.async_reload_accessories([ENTITY_ID])
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_automatic_keeps_explicit_choice(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an explicit type updates the stored routing for automatic."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    # A new entity picks the HeaterCooler and the choice is stored
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "HeaterCooler"
    await _async_stop_bridge(homekit)

    # An explicit Thermostat overrides and updates the stored routing
    homekit = await _async_start_bridge(
        hass, entry, {ENTITY_ID: {CONF_TYPE: "thermostat"}}
    )
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "Thermostat"
    await _async_stop_bridge(homekit)

    # Back on automatic the entity keeps the Thermostat and is offered
    # the repair instead of flipping back to the HeaterCooler
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "Thermostat"
    assert issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_accessory_mode_reload_resyncs_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an accessory mode reload keeps the repair issue in sync."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(
        hass, entry, homekit_mode=HOMEKIT_MODE_ACCESSORY, existing_pairing=True
    )
    issue_id = accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    # Losing the fan speeds makes the entity ineligible, so a reload
    # removes the stale issue
    hass.states.async_set(
        ENTITY_ID,
        HVACMode.COOL,
        INELIGIBLE_ATTRS,
    )
    await homekit.async_reload_accessories([ENTITY_ID])
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_accessory_mode_new_pairing_routes_heater_cooler(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a brand new accessory mode pairing picks the HeaterCooler."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(
        hass, entry, homekit_mode=HOMEKIT_MODE_ACCESSORY
    )

    assert type(homekit.driver.accessory).__name__ == "HeaterCooler"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_explicit_heater_cooler_wins_over_humidity_safeguard(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an explicit heater_cooler type wins for a humidity entity."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass_storage[get_aid_storage_filename_for_entry_id(entry.entry_id)] = {
        "version": 1,
        "data": {"allocations": {ENTITY_ID: 1234567}},
    }
    hass.states.async_set(
        ENTITY_ID,
        HVACMode.COOL,
        HUMIDITY_ATTRS,
    )

    homekit = await _async_start_bridge(
        hass, entry, {ENTITY_ID: {CONF_TYPE: "heater_cooler"}}
    )

    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "HeaterCooler"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_explicit_type_never_raises_issue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity with a configured type is not a repair candidate."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass_storage[get_aid_storage_filename_for_entry_id(entry.entry_id)] = {
        "version": 1,
        "data": {"allocations": {ENTITY_ID: 1234567}},
    }
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(
        hass, entry, {ENTITY_ID: {CONF_TYPE: "thermostat"}}
    )

    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "Thermostat"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_yaml_bridge_never_raises_issue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a YAML configured bridge keeps the Thermostat without a repair."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        source=SOURCE_IMPORT,
    )
    entry.add_to_hass(hass)
    hass_storage[get_aid_storage_filename_for_entry_id(entry.entry_id)] = {
        "version": 1,
        "data": {"allocations": {ENTITY_ID: 1234567}},
    }
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    accessories = list(homekit.bridge.accessories.values())
    assert type(accessories[0]).__name__ == "Thermostat"
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_stale_issue_removed_on_start(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue for an entity that is no longer a candidate is removed."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    stale_issue_id = _create_candidate_issue(hass, entry, "climate.gone")
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    assert not issue_registry.async_get_issue(DOMAIN, stale_issue_id)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_repair_flow_opts_entity_into_heater_cooler(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the fix flow writes the type into the entry options."""
    assert await async_setup_component(hass, "repairs", {})
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    with patch(f"{PATH_HOMEKIT}.HomeKit.async_start"):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        issue_id = _create_candidate_issue(hass, entry, ENTITY_ID)

        client = await hass_client()
        result = await start_repair_fix_flow(client, DOMAIN, issue_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "confirm"

        # Confirming writes the type and reloads the bridge
        result = await process_repair_fix_flow(client, result["flow_id"], json={})
        assert result["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    assert entry.options[CONF_ENTITY_CONFIG][ENTITY_ID][CONF_TYPE] == "heater_cooler"
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_remove_entry_deletes_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test removing the entry deletes its repair issues."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    issue_id = _create_candidate_issue(hass, entry, ENTITY_ID)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await async_remove_entry(hass, entry)

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_second_bridge_gets_its_own_issue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the same entity bridged by two entries gets per entry issues."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "other_name", CONF_PORT: 12346}
    )
    other.add_to_hass(hass)
    for cfg in (entry, other):
        hass_storage[get_aid_storage_filename_for_entry_id(cfg.entry_id)] = {
            "version": 1,
            "data": {"allocations": {ENTITY_ID: 1234567}},
        }
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    # Only this bridge's issue exists; the other bridge has not started
    assert issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(entry.entry_id, ENTITY_ID)
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, accessory_type_issue_id(other.entry_id, ENTITY_ID)
    )
    await _async_stop_bridge(homekit)
