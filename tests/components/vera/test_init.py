"""Vera tests."""
import pyvera as pv
from requests.exceptions import RequestException

from homeassistant.components.vera import CONF_CONTROLLER, DOMAIN
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
