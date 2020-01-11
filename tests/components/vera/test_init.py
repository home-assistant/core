"""Vera tests."""
from asynctest import MagicMock
import pyvera as pv
from requests.exceptions import RequestException

from homeassistant import config_entries
from homeassistant.components.vera import (
    CONF_CONTROLLER,
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS, CONF_SOURCE
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

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


async def test_async_setup_update_configs(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_CONTROLLER: "http://url1:123",
            CONF_SOURCE: config_entries.SOURCE_IMPORT,
        },
    )
    entry1.add_to_hass(hass)

    await vera_component_factory.configure_component(
        hass,
        new_simple_controller_config(
            config={CONF_CONTROLLER: "http://url2:123"},
            options={CONF_LIGHTS: [1, 2], CONF_EXCLUDE: [3, 4]},
            config_from_file=True,
        ),
    )

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    entry = entries[0]
    assert entry.data == {
        CONF_CONTROLLER: "http://url2:123",
        CONF_SOURCE: config_entries.SOURCE_IMPORT,
    }
    assert entry.options == {CONF_LIGHTS: [1, 2], CONF_EXCLUDE: [3, 4]}


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
        await async_unload_entry(hass, config_entry)


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
    entry = MagicMock(spec=ConfigEntry)  # type: ConfigEntry
    entry.data = {CONF_CONTROLLER: "http://127.0.0.1"}

    assert not await async_setup_entry(hass, entry)
