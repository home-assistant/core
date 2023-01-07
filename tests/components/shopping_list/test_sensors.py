""" Unit tests for the ShoppingList component's sensors """
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.components.shopping_list import ShoppingData
from homeassistant.components.shopping_list.const import DOMAIN


@pytest.mark.usefixtures("init_integration")
async def test_default_all_sensors_zero(hass: HomeAssistant):
    """By default (i.e. when the list is empty) all sensors should be zero"""
    # Given
    data: ShoppingData = hass.data[DOMAIN]
    assert len(data.items) == 0

    # When
    incomplete_sensor = hass.states.get("sensor.shopping_list_incomplete_items")
    completed_sensor = hass.states.get("sensor.shopping_list_completed_items")
    total_sensor = hass.states.get("sensor.shopping_list_total_items")

    # Then
    assert incomplete_sensor
    assert total_sensor

    assert incomplete_sensor.state == "0"
    assert total_sensor.state == "0"
    assert completed_sensor.state == "0"


@pytest.mark.usefixtures("init_integration")
async def test_incomplete_items_add_to_total(hass: HomeAssistant):
    """Any items that are not marked as completed will add to total and incomplete sensor"""
    # Given
    data: ShoppingData = hass.data[DOMAIN]
    await data.async_add("Food")
    await hass.async_block_till_done()

    # When
    incomplete_sensor = hass.states.get("sensor.shopping_list_incomplete_items")
    completed_sensor = hass.states.get("sensor.shopping_list_completed_items")
    total_sensor = hass.states.get("sensor.shopping_list_total_items")

    # Then``
    assert incomplete_sensor
    assert total_sensor

    assert incomplete_sensor.state == "1"
    assert total_sensor.state == "1"
    assert completed_sensor.state == "0"


@pytest.mark.usefixtures("init_integration")
async def test_completed_item_adds_to_right_sensor(hass: HomeAssistant):
    """Any items that are marked as completed will add to total and completed but not incomplete sensor"""
    # Given
    data: ShoppingData = hass.data[DOMAIN]
    await data.async_add("Beer")
    burgers = await data.async_add("Burgers")
    await data.async_update(burgers["id"], {"complete": True})
    await data.async_add("Buns")
    await hass.async_block_till_done()

    # When
    incomplete_sensor = hass.states.get("sensor.shopping_list_incomplete_items")
    completed_sensor = hass.states.get("sensor.shopping_list_completed_items")
    total_sensor = hass.states.get("sensor.shopping_list_total_items")

    # Then
    assert incomplete_sensor
    assert total_sensor

    assert incomplete_sensor.state == "2"
    assert total_sensor.state == "3"
    assert completed_sensor.state == "1"


@pytest.mark.usefixtures("init_integration")
async def test_removing_items_updates_counts(hass: HomeAssistant):
    """Removing an item updates the counts for totals and incomplete items"""
    # Given
    data: ShoppingData = hass.data[DOMAIN]
    await data.async_add("Beer")
    burgers = await data.async_add("Burgers")
    await data.async_update(burgers["id"], {"complete": True})
    buns = await data.async_add("Buns")
    await hass.async_block_till_done()
    await data.async_remove(buns["id"])
    await hass.async_block_till_done()

    # When
    incomplete_sensor = hass.states.get("sensor.shopping_list_incomplete_items")
    completed_sensor = hass.states.get("sensor.shopping_list_completed_items")
    total_sensor = hass.states.get("sensor.shopping_list_total_items")

    # Then
    assert incomplete_sensor
    assert total_sensor

    assert incomplete_sensor.state == "1"
    assert total_sensor.state == "2"
    assert completed_sensor.state == "1"
