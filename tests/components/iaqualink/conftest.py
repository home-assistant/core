"""Configuration for iAquaLink tests."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, PropertyMock, patch

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkDevice
from iaqualink.system import AqualinkSystem
from iaqualink.systems.iaqua.device import (
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaLightSwitch,
    IaquaSensor,
    IaquaThermostat,
)
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iaqualink import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

MOCK_USERNAME = "test@example.com"
MOCK_PASSWORD = "password"
MOCK_DATA = {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD}


@dataclass
class SystemDevices:
    """All devices created by setup_integration."""

    system: IaquaSystem
    switch: IaquaAuxSwitch
    light: IaquaLightSwitch
    binary_sensor: IaquaBinarySensor
    sensor: IaquaSensor
    thermostat: IaquaThermostat
    heater: IaquaAuxSwitch
    pool_temp: IaquaSensor


@pytest.fixture(name="client")
def client_fixture():
    """Create client fixture."""
    return AqualinkClient(username=MOCK_USERNAME, password=MOCK_PASSWORD)


def get_aqualink_system(aqualink, cls=None, data=None):
    """Create aqualink system."""
    if cls is None:
        cls = AqualinkSystem

    if data is None:
        data = {}

    data["name"] = "Pool"
    data["serial_number"] = "SN00001"

    return cls(aqualink=aqualink, data=data)


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> SystemDevices:
    """Set up the iAquaLink integration with all platform entities."""
    system = get_aqualink_system(
        client,
        cls=IaquaSystem,
        data={"home_screen": [{}, {}, {}, {"temp_scale": "F"}]},
    )
    system.online = True

    async def update() -> None:
        system.temp_unit = "F"

    system.update = AsyncMock(side_effect=update)

    switch = get_aqualink_device(
        system, name="aux_1", cls=IaquaAuxSwitch, data={"state": "1", "aux": "1"}
    )
    light = get_aqualink_device(
        system,
        name="aux_2",
        cls=IaquaLightSwitch,
        data={"state": "1", "aux": "2", "label": "Pool Light"},
    )
    binary_sensor = get_aqualink_device(
        system, name="freeze_protection", cls=IaquaBinarySensor, data={"state": "1"}
    )
    sensor = get_aqualink_device(
        system, name="ph", cls=IaquaSensor, data={"state": "7.2"}
    )
    thermostat = get_aqualink_device(
        system, name="pool_set_point", cls=IaquaThermostat, data={"state": "84"}
    )
    heater = get_aqualink_device(
        system, name="pool_heater", cls=IaquaAuxSwitch, data={"state": "1", "aux": "3"}
    )
    pool_temp = get_aqualink_device(
        system, name="pool_temp", cls=IaquaSensor, data={"state": "80"}
    )

    platform_devices = {
        d.name: d for d in (switch, light, binary_sensor, sensor, thermostat)
    }
    system.devices = {
        **platform_devices,
        heater.name: heater,
        pool_temp.name: pool_temp,
    }
    system.get_devices = AsyncMock(return_value=platform_devices)
    system.set_aux = AsyncMock()
    system.set_temps = AsyncMock()
    system.set_light = AsyncMock()

    await setup_entry(hass, config_entry, system)

    return SystemDevices(
        system=system,
        switch=switch,
        light=light,
        binary_sensor=binary_sensor,
        sensor=sensor,
        thermostat=thermostat,
        heater=heater,
        pool_temp=pool_temp,
    )


async def setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    system: AqualinkSystem,
) -> None:
    """Set up a config entry with a pre-built system."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value={system.serial: system},
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def assert_platform_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    domain: str,
) -> None:
    """Assert all entities for a given platform domain are set up correctly."""
    await setup_integration(hass, config_entry, client)

    entity_entries = [
        e
        for e in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if e.domain == domain
    ]
    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


def get_aqualink_device(system, name, cls=None, data=None):
    """Create aqualink device."""
    if cls is None:
        cls = AqualinkDevice

        # AqualinkDevice doesn't implement some of the properties since it's left to
        # sub-classes for them to do. Provide a basic implementation here for the
        # benefits of the test suite.
        attrs = {
            "name": name,
            "manufacturer": "Jandy",
            "model": "Device",
            "label": name.upper(),
        }

        for k, v in attrs.items():
            patcher = patch.object(cls, k, new_callable=PropertyMock)
            mock = patcher.start()
            mock.return_value = v

    if data is None:
        data = {}

    data["name"] = name

    return cls(system=system, data=data)


@pytest.fixture(name="config_data")
def config_data_fixture():
    """Create hass config fixture."""
    return MOCK_DATA


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: MOCK_DATA}


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
    )
