"""Test the Min/Max integration."""

from homeassistant.components.generic_hygrostat import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_entry_changed(hass: HomeAssistant) -> None:
    """Test reconfiguring."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    def _create_mock_entity(domain: str, name: str) -> er.RegistryEntry:
        config_entry = MockConfigEntry(
            data={},
            domain="test",
            title=f"{name}",
        )
        config_entry.add_to_hass(hass)
        device_entry = device_registry.async_get_or_create(
            identifiers={("test", name)}, config_entry_id=config_entry.entry_id
        )
        return entity_registry.async_get_or_create(
            domain, "test", name, suggested_object_id=name, device_id=device_entry.id
        )

    def _get_device_config_entries(entry: er.RegistryEntry) -> set[str]:
        assert entry.device_id
        device = device_registry.async_get(entry.device_id)
        assert device
        return device.config_entries

    # Set up entities, with backing devices and config entries
    initial_entry = _create_mock_entity("switch", "initial")
    changed_entry = _create_mock_entity("switch", "changed")

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "device_class": "dehumidifier",
            "dry_tolerance": 2.0,
            "humidifier": "switch.initial",
            "name": "My dehumidifier",
            "target_sensor": "sensor.humidity",
            "wet_tolerance": 4.0,
        },
        title="My integration",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.entry_id in _get_device_config_entries(initial_entry)
    assert config_entry.entry_id not in _get_device_config_entries(changed_entry)

    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "humidifier": "switch.changed"}
    )
    await hass.async_block_till_done()

    # Check that the config entry association has updated
    assert config_entry.entry_id not in _get_device_config_entries(initial_entry)
    assert config_entry.entry_id in _get_device_config_entries(changed_entry)
