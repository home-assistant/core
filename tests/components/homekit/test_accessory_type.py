"""Test the HomeKit accessory type routing."""

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
from homeassistant.components.homekit import HomeKit
from homeassistant.components.homekit.const import (
    DEFAULT_PORT,
    DOMAIN,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODE_BRIDGE,
    PERSIST_LOCK_DATA,
)
from homeassistant.components.homekit.type_heater_coolers import HeaterCooler
from homeassistant.components.homekit.type_thermostats import Thermostat
from homeassistant.components.homekit.util import get_aid_storage_filename_for_entry_id
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_EXCLUDE_ENTITY_GLOBS,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
    convert_filter,
)

from .util import PATH_HOMEKIT

from tests.common import MockConfigEntry


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


HUMIDITY_ATTRS = {
    **CAPABLE_ATTRS,
    ATTR_SUPPORTED_FEATURES: (
        CAPABLE_ATTRS[ATTR_SUPPORTED_FEATURES] | ClimateEntityFeature.TARGET_HUMIDITY
    ),
}


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
async def test_existing_entity_stays_thermostat(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test a previously bridged entity keeps the Thermostat."""
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
    assert isinstance(accessories[0], Thermostat)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_new_entity_routes_to_heater_cooler(
    hass: HomeAssistant,
) -> None:
    """Test a never bridged entity gets the HeaterCooler."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    accessories = list(homekit.bridge.accessories.values())
    assert len(accessories) == 1
    assert isinstance(accessories[0], HeaterCooler)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_reset_does_not_allocate_for_unbridged_entities(
    hass: HomeAssistant,
) -> None:
    """Test resetting an entity another bridge owns does not allocate."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)

    # The reset service fans out to every instance, so an allocation here
    # would wrongly mark the entity as previously bridged
    await homekit.async_reset_accessories(["climate.not_bridged_here"])
    assert homekit.aid_storage is not None
    assert (
        homekit.aid_storage.get_allocated_aid_for_entity_id("climate.not_bridged_here")
        is None
    )
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_failed_accessory_creation_is_not_recorded(
    hass: HomeAssistant,
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
    assert isinstance(accessories[0], HeaterCooler)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_heater_cooler_choice_survives_restart(
    hass: HomeAssistant,
) -> None:
    """Test the automatic HeaterCooler choice persists across restarts."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert isinstance(accessories[0], HeaterCooler)
    await _async_stop_bridge(homekit)

    # The entity now has an aid allocation, so only the stored choice
    # keeps it on the HeaterCooler after a restart.
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert isinstance(accessories[0], HeaterCooler)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_gained_humidity_setpoint_drops_stored_choice(
    hass: HomeAssistant,
) -> None:
    """Test a stored HeaterCooler choice is dropped for a humidity setpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert isinstance(accessories[0], HeaterCooler)
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
    assert isinstance(accessories[0], Thermostat)
    assert homekit.aid_storage is not None
    assert homekit.aid_storage.get_accessory_type(ENTITY_ID) is None
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_automatic_keeps_explicit_choice(
    hass: HomeAssistant,
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
    assert isinstance(accessories[0], HeaterCooler)
    await _async_stop_bridge(homekit)

    # An explicit Thermostat overrides and updates the stored routing
    homekit = await _async_start_bridge(
        hass, entry, {ENTITY_ID: {CONF_TYPE: "thermostat"}}
    )
    accessories = list(homekit.bridge.accessories.values())
    assert isinstance(accessories[0], Thermostat)
    await _async_stop_bridge(homekit)

    # Back on automatic the entity keeps the Thermostat instead of
    # flipping back to the HeaterCooler
    homekit = await _async_start_bridge(hass, entry)
    accessories = list(homekit.bridge.accessories.values())
    assert isinstance(accessories[0], Thermostat)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_accessory_mode_existing_pairing_stays_thermostat(
    hass: HomeAssistant,
) -> None:
    """Test an existing accessory mode pairing keeps the Thermostat."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    homekit = await _async_start_bridge(
        hass, entry, homekit_mode=HOMEKIT_MODE_ACCESSORY, existing_pairing=True
    )

    assert isinstance(homekit.driver.accessory, Thermostat)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_stored_thermostat_survives_pairing_reset(
    hass: HomeAssistant,
) -> None:
    """Test a stored Thermostat choice is kept when the entity looks new."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)
    hass.states.async_set(ENTITY_ID, HVACMode.COOL, CAPABLE_ATTRS)

    # An explicit Thermostat choice is stored with the accessory
    homekit = await _async_start_bridge(
        hass,
        entry,
        {ENTITY_ID: {CONF_TYPE: "thermostat"}},
        homekit_mode=HOMEKIT_MODE_ACCESSORY,
    )
    assert isinstance(homekit.driver.accessory, Thermostat)
    await _async_stop_bridge(homekit)

    # A pairing reset makes the entry look brand new, but Automatic still
    # keeps the stored Thermostat instead of flipping to the HeaterCooler
    homekit = await _async_start_bridge(
        hass, entry, homekit_mode=HOMEKIT_MODE_ACCESSORY
    )
    assert isinstance(homekit.driver.accessory, Thermostat)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_accessory_mode_new_pairing_routes_heater_cooler(
    hass: HomeAssistant,
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

    assert isinstance(homekit.driver.accessory, HeaterCooler)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_explicit_heater_cooler_wins_over_humidity_safeguard(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
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
    assert isinstance(accessories[0], HeaterCooler)
    await _async_stop_bridge(homekit)


@pytest.mark.usefixtures("mock_async_zeroconf", "hk_driver")
async def test_explicit_type_wins_for_existing_entity(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test an entity with a configured type uses it."""
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
    assert isinstance(accessories[0], Thermostat)
    await _async_stop_bridge(homekit)
