"""The tests for the Met Office sensor component."""

import datetime
import json

import pytest
import requests_mock

from homeassistant.components.metoffice.const import ATTRIBUTION, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    DEVICE_KEY_KINGSLYNN,
    DEVICE_KEY_WAVERTREE,
    KINGSLYNN_SENSOR_RESULTS,
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    TEST_DATETIME_STRING,
    TEST_SITE_NAME_KINGSLYNN,
    TEST_SITE_NAME_WAVERTREE,
    WAVERTREE_SENSOR_RESULTS,
)

from tests.common import MockConfigEntry, load_fixture


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_one_sensor_site_running(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test the Met Office sensor platform."""
    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json", "metoffice"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly",
        text=wavertree_hourly,
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily",
        text=wavertree_daily,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 1
    device_wavertree = device_registry.async_get_device(
        identifiers=DEVICE_KEY_WAVERTREE
    )
    assert device_wavertree.name == "Met Office Wavertree"

    running_sensor_ids = hass.states.async_entity_ids("sensor")
    assert len(running_sensor_ids) > 0
    for running_id in running_sensor_ids:
        sensor = hass.states.get(running_id)
        sensor_id = sensor.attributes.get("sensor_id")
        _, sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]

        assert sensor.state == sensor_value
        assert sensor.attributes.get("last_update").isoformat() == TEST_DATETIME_STRING
        assert sensor.attributes.get("site_id") == "354107"
        assert sensor.attributes.get("site_name") == TEST_SITE_NAME_WAVERTREE
        assert sensor.attributes.get("attribution") == ATTRIBUTION


@pytest.mark.freeze_time(datetime.datetime(2020, 4, 25, 12, tzinfo=datetime.UTC))
async def test_two_sensor_sites_running(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test we handle two sets of sensors running for two different sites."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json", "metoffice"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=daily", text=wavertree_daily
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=3hourly", text=kingslynn_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=daily", text=kingslynn_daily
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_KINGSLYNN,
    )
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    assert len(device_registry.devices) == 2
    device_kingslynn = device_registry.async_get_device(
        identifiers=DEVICE_KEY_KINGSLYNN
    )
    assert device_kingslynn.name == "Met Office King's Lynn"
    device_wavertree = device_registry.async_get_device(
        identifiers=DEVICE_KEY_WAVERTREE
    )
    assert device_wavertree.name == "Met Office Wavertree"

    running_sensor_ids = hass.states.async_entity_ids("sensor")
    assert len(running_sensor_ids) > 0
    for running_id in running_sensor_ids:
        sensor = hass.states.get(running_id)
        sensor_id = sensor.attributes.get("sensor_id")
        if sensor.attributes.get("site_id") == "354107":
            _, sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]
            assert sensor.state == sensor_value
            assert (
                sensor.attributes.get("last_update").isoformat() == TEST_DATETIME_STRING
            )
            assert sensor.attributes.get("sensor_id") == sensor_id
            assert sensor.attributes.get("site_id") == "354107"
            assert sensor.attributes.get("site_name") == TEST_SITE_NAME_WAVERTREE
            assert sensor.attributes.get("attribution") == ATTRIBUTION

        else:
            _, sensor_value = KINGSLYNN_SENSOR_RESULTS[sensor_id]
            assert sensor.state == sensor_value
            assert (
                sensor.attributes.get("last_update").isoformat() == TEST_DATETIME_STRING
            )
            assert sensor.attributes.get("sensor_id") == sensor_id
            assert sensor.attributes.get("site_id") == "322380"
            assert sensor.attributes.get("site_name") == TEST_SITE_NAME_KINGSLYNN
            assert sensor.attributes.get("attribution") == ATTRIBUTION
