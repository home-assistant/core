"""Vera tests."""
from unittest.mock import MagicMock

import pytest
import pyvera as pv
from requests.exceptions import RequestException

from homeassistant.components.vera import (
    CONF_CONTROLLER,
    CONF_EXCLUDE,
    CONF_LIGHTS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ComponentFactory, ConfigSource, new_simple_controller_config

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = vera_device1.device_id
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False
    entity1_id = "binary_sensor.first_dev_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_source=ConfigSource.CONFIG_FLOW,
            serial_number="first_serial",
            devices=(vera_device1,),
        ),
    )

    entity_registry = er.async_get(hass)
    entry1 = entity_registry.async_get(entity1_id)
    assert entry1
    assert entry1.unique_id == "vera_first_serial_1"


async def test_init_from_file(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = vera_device1.device_id
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False
    entity1_id = "binary_sensor.first_dev_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_source=ConfigSource.FILE,
            serial_number="first_serial",
            devices=(vera_device1,),
        ),
    )

    entity_registry = er.async_get(hass)
    entry1 = entity_registry.async_get(entity1_id)
    assert entry1
    assert entry1.unique_id == "vera_first_serial_1"


async def test_multiple_controllers_with_legacy_one(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test multiple controllers with one legacy controller."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = vera_device1.device_id
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False
    entity1_id = "binary_sensor.first_dev_1"

    vera_device2: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device2.device_id = 2
    vera_device2.vera_device_id = vera_device2.device_id
    vera_device2.name = "second_dev"
    vera_device2.is_tripped = False
    entity2_id = "binary_sensor.second_dev_2"

    # Add existing entity registry entry from previous setup.
    entity_registry.async_get_or_create(
        domain="switch", platform=DOMAIN, unique_id="12"
    )

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_source=ConfigSource.FILE,
            serial_number="first_serial",
            devices=(vera_device1,),
        ),
    )

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:222"},
            config_source=ConfigSource.CONFIG_FLOW,
            serial_number="second_serial",
            devices=(vera_device2,),
        ),
    )

    entity_registry = er.async_get(hass)

    entry1 = entity_registry.async_get(entity1_id)
    assert entry1
    assert entry1.unique_id == "1"

    entry2 = entity_registry.async_get(entity2_id)
    assert entry2
    assert entry2.unique_id == "vera_second_serial_2"


async def test_unload(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = vera_device1.device_id
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False

    await vera_component_factory.configure_component(
        hass=hass, controller_config=new_simple_controller_config()
    )

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries

    for config_entry in entries:
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_error(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""

    def setup_callback(controller: pv.VeraController) -> None:
        controller.get_devices.side_effect = RequestException()
        controller.get_scenes.side_effect = RequestException()

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(setup_callback=setup_callback),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_CONTROLLER: "http://127.0.0.1"},
        options={},
        unique_id="12345",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)


@pytest.mark.parametrize(
    "options",
    [
        {CONF_LIGHTS: [4, 10, 12, "AAA"], CONF_EXCLUDE: [1, "BBB"]},
        {CONF_LIGHTS: ["4", "10", "12", "AAA"], CONF_EXCLUDE: ["1", "BBB"]},
    ],
)
async def test_exclude_and_light_ids(
    hass: HomeAssistant, vera_component_factory: ComponentFactory, options
) -> None:
    """Test device exclusion, marking switches as lights and fixing the data type."""
    vera_device1: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "dev1"
    vera_device1.is_tripped = False
    entity_id1 = "binary_sensor.dev1_1"

    vera_device2: pv.VeraBinarySensor = MagicMock(spec=pv.VeraBinarySensor)
    vera_device2.device_id = 2
    vera_device2.vera_device_id = 2
    vera_device2.name = "dev2"
    vera_device2.is_tripped = False
    entity_id2 = "binary_sensor.dev2_2"

    vera_device3: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_device3.device_id = 3
    vera_device3.vera_device_id = 3
    vera_device3.name = "dev3"
    vera_device3.category = pv.CATEGORY_SWITCH
    vera_device3.is_switched_on = MagicMock(return_value=False)

    entity_id3 = "switch.dev3_3"

    vera_device4: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_device4.device_id = 4
    vera_device4.vera_device_id = 4
    vera_device4.name = "dev4"
    vera_device4.category = pv.CATEGORY_SWITCH
    vera_device4.is_switched_on = MagicMock(return_value=False)
    vera_device4.get_brightness = MagicMock(return_value=0)
    vera_device4.get_color = MagicMock(return_value=[0, 0, 0])
    vera_device4.is_dimmable = True

    entity_id4 = "light.dev4_4"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config_source=ConfigSource.CONFIG_ENTRY,
            devices=(vera_device1, vera_device2, vera_device3, vera_device4),
            config={**{CONF_CONTROLLER: "http://127.0.0.1:123"}, **options},
        ),
    )

    # Assert the entries were setup correctly.
    config_entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    assert config_entry.options[CONF_LIGHTS] == [4, 10, 12]
    assert config_entry.options[CONF_EXCLUDE] == [1]

    update_callback = component_data.controller_data[0].update_callback

    update_callback(vera_device1)
    update_callback(vera_device2)
    update_callback(vera_device3)
    update_callback(vera_device4)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id1) is None
    assert hass.states.get(entity_id2) is not None
    assert hass.states.get(entity_id3) is not None
    assert hass.states.get(entity_id4) is not None
