"""The tests for the Sure Petcare binary sensor platform."""
from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.setup import async_setup_component

from . import MOCK_API_DATA, MOCK_CONFIG, _patch_sensor_setup


async def test_unique_ids(hass, surepetcare) -> None:
    """Test the generation of unique ids."""
    instance = surepetcare.return_value
    instance.data = MOCK_API_DATA
    instance.get_data.return_value = MOCK_API_DATA

    with _patch_sensor_setup():
        assert await async_setup_component(hass, DOMAIN, MOCK_CONFIG)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    assert hass.states.get("binary_sensor.hub_hub")
    hub = entity_registry.async_get("binary_sensor.hub_hub")
    assert hub.unique_id == ""

    assert hass.states.get("binary_sensor.cat_flap_cat_flap")
    cat_flap = entity_registry.async_get("binary_sensor.cat_flap_cat_flap")
    assert cat_flap.unique_id == ""

    assert hass.states.get("binary_sensor.cat_flap_cat_flap_connectivity")
    cat_flap_conn = entity_registry.async_get(
        "binary_sensor.cat_flap_cat_flap_connectivity"
    )
    assert cat_flap_conn.unique_id == ""

    assert hass.states.get("binary_sensor.pet_flap_pet_flap")
    pet_flap = entity_registry.async_get("binary_sensor.pet_flap_pet_flap")
    assert pet_flap.unique_id == ""

    assert hass.states.get("binary_sensor.pet_flap_pet_flap_connectivity")
    pet_flap_conn = entity_registry.async_get(
        "binary_sensor.pet_flap_pet_flap_connectivity"
    )
    assert pet_flap_conn.unique_id == ""

    assert hass.states.get("binary_sensor.feeder_feeder")
    feeder = entity_registry.async_get("binary_sensor.feeder_feeder")
    assert feeder.unique_id == ""

    assert hass.states.get("binary_sensor.feeder_feeder_connectivity")
    feeder_conn = entity_registry.async_get("binary_sensor.feeder_feeder_connectivity")
    assert feeder_conn.unique_id == ""

    assert hass.states.get("binary_sensor.pet_pet")
    pet = entity_registry.async_get("binary_sensor.pet_pet")
    assert pet.unique_id == ""
