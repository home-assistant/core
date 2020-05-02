"""Vera tests."""
import pytest
import pyvera as pv
from requests.exceptions import RequestException

from homeassistant.components.vera import (
    CONF_CONTROLLER,
    CONF_EXCLUDE,
    CONF_LIGHTS,
    DOMAIN,
)
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock
from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1 = MagicMock(spec=pv.VeraBinarySensor)  # type: pv.VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False
    entity1_id = "binary_sensor.first_dev_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_from_file=False,
            serial_number="first_serial",
            devices=(vera_device1,),
        ),
    )

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry1 = entity_registry.async_get(entity1_id)

    assert entry1


async def test_init_from_file(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1 = MagicMock(spec=pv.VeraBinarySensor)  # type: pv.VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False
    entity1_id = "binary_sensor.first_dev_1"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            config={CONF_CONTROLLER: "http://127.0.0.1:111"},
            config_from_file=True,
            serial_number="first_serial",
            devices=(vera_device1,),
        ),
    )

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry1 = entity_registry.async_get(entity1_id)
    assert entry1


async def test_unload(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1 = MagicMock(spec=pv.VeraBinarySensor)  # type: pv.VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False

    await vera_component_factory.configure_component(
        hass=hass, controller_config=new_simple_controller_config()
    )

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries

    for config_entry in entries:
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state == ENTRY_STATE_NOT_LOADED


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
    ["options"],
    [
        [{CONF_LIGHTS: [4, 10, 12, "AAA"], CONF_EXCLUDE: [1, "BBB"]}],
        [{CONF_LIGHTS: ["4", "10", "12", "AAA"], CONF_EXCLUDE: ["1", "BBB"]}],
    ],
)
async def test_exclude_and_light_ids(
    hass: HomeAssistant, vera_component_factory: ComponentFactory, options
) -> None:
    """Test device exclusion, marking switches as lights and fixing the data type."""
    vera_device1 = MagicMock(spec=pv.VeraBinarySensor)  # type: pv.VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "dev1"
    vera_device1.is_tripped = False
    entity_id1 = "binary_sensor.dev1_1"

    vera_device2 = MagicMock(spec=pv.VeraBinarySensor)  # type: pv.VeraBinarySensor
    vera_device2.device_id = 2
    vera_device2.vera_device_id = 2
    vera_device2.name = "dev2"
    vera_device2.is_tripped = False
    entity_id2 = "binary_sensor.dev2_2"

    vera_device3 = MagicMock(spec=pv.VeraSwitch)  # type: pv.VeraSwitch
    vera_device3.device_id = 3
    vera_device3.name = "dev3"
    vera_device3.category = pv.CATEGORY_SWITCH
    vera_device3.is_switched_on = MagicMock(return_value=False)
    entity_id3 = "switch.dev3_3"

    vera_device4 = MagicMock(spec=pv.VeraSwitch)  # type: pv.VeraSwitch
    vera_device4.device_id = 4
    vera_device4.name = "dev4"
    vera_device4.category = pv.CATEGORY_SWITCH
    vera_device4.is_switched_on = MagicMock(return_value=False)
    entity_id4 = "light.dev4_4"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            devices=(vera_device1, vera_device2, vera_device3, vera_device4),
            config={**{CONF_CONTROLLER: "http://127.0.0.1:123"}, **options},
        ),
    )

    # Assert the entries were setup correctly.
    config_entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    assert config_entry.options == {
        CONF_LIGHTS: [4, 10, 12],
        CONF_EXCLUDE: [1],
    }

    update_callback = component_data.controller_data.update_callback

    update_callback(vera_device1)
    update_callback(vera_device2)
    update_callback(vera_device3)
    update_callback(vera_device4)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id1) is None
    assert hass.states.get(entity_id2) is not None
    assert hass.states.get(entity_id3) is not None
    assert hass.states.get(entity_id4) is not None
