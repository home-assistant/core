"""The tests for the Met Office sensor component."""

import datetime
import json
import re

import pytest
import requests_mock

from homeassistant.components.metoffice.const import ATTRIBUTION, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    DEVICE_KEY_KINGSLYNN,
    DEVICE_KEY_WAVERTREE,
    KINGSLYNN_SENSOR_RESULTS,
    METOFFICE_CONFIG_KINGSLYNN,
    METOFFICE_CONFIG_WAVERTREE,
    TEST_DATETIME_STRING,
    TEST_LATITUDE_WAVERTREE,
    TEST_LONGITUDE_WAVERTREE,
    WAVERTREE_SENSOR_RESULTS,
)

from tests.common import MockConfigEntry, load_fixture


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_one_sensor_site_running(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test the Met Office sensor platform."""
    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json", "metoffice"))
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
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
        sensor_id = re.search("met_office_wavertree_(.+?)$", running_id).group(1)
        sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]

        assert sensor.state == sensor_value
        assert sensor.attributes.get("last_update").isoformat() == TEST_DATETIME_STRING
        assert sensor.attributes.get("attribution") == ATTRIBUTION


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
async def test_two_sensor_sites_running(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test we handle two sets of sensors running for two different sites."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json", "metoffice"))
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])
    kingslynn_daily = json.dumps(mock_json["kingslynn_daily"])

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=kingslynn_hourly,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=kingslynn_daily,
    )

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
        if "wavertree" in running_id:
            sensor_id = re.search("met_office_wavertree_(.+?)$", running_id).group(1)
            sensor_value = WAVERTREE_SENSOR_RESULTS[sensor_id]
            assert sensor.state == sensor_value
            assert (
                sensor.attributes.get("last_update").isoformat() == TEST_DATETIME_STRING
            )
            assert sensor.attributes.get("attribution") == ATTRIBUTION

        else:
            sensor_id = re.search("met_office_king_s_lynn_(.+?)$", running_id).group(1)
            sensor_value = KINGSLYNN_SENSOR_RESULTS[sensor_id]
            assert sensor.state == sensor_value
            assert (
                sensor.attributes.get("last_update").isoformat() == TEST_DATETIME_STRING
            )
            assert sensor.attributes.get("attribution") == ATTRIBUTION


@pytest.mark.freeze_time(datetime.datetime(2024, 11, 23, 12, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    ("old_unique_id"),
    [
        f"visibility_distance_{TEST_LATITUDE_WAVERTREE}_{TEST_LONGITUDE_WAVERTREE}",
        f"visibility_distance_{TEST_LATITUDE_WAVERTREE}_{TEST_LONGITUDE_WAVERTREE}_daily",
    ],
)
async def test_legacy_entities_are_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    old_unique_id: str,
) -> None:
    """Test the expected entities are deleted."""
    mock_json = json.loads(load_fixture("metoffice.json", "metoffice"))
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    wavertree_daily = json.dumps(mock_json["wavertree_daily"])

    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=wavertree_hourly,
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=wavertree_daily,
    )
    # Pre-create the entity
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        unique_id=old_unique_id,
        suggested_object_id="met_office_wavertree_visibility_distance",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=METOFFICE_CONFIG_WAVERTREE,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
