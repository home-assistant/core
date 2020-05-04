"""The data tests for the Met Office weather component."""
import json
import logging

from asynctest import patch

from homeassistant.components.metoffice.const import ATTRIBUTION, DOMAIN

from . import MockDateTime
from .const import (
    CONFIG_KINGSLYNN_3HOURLY,
    CONFIG_WAVERTREE_3HOURLY,
    DATETIME_FORMAT,
    EXPECTED_KINGSLYNN_SENSOR_RESULTS,
    EXPECTED_WAVERTREE_SENSOR_RESULTS,
    TEST_DATETIME_STRING,
    TEST_SITE_NAME_KINGSLYNN,
    TEST_SITE_NAME_WAVERTREE,
)

from tests.common import MockConfigEntry, load_fixture

_LOGGER = logging.getLogger(__name__)


@patch("datetime.datetime", MockDateTime)
async def test_one_sensor_site_running_3hourly(hass, requests_mock):
    """Test the Met Office sensor platform."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly,
    )

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    running_sensor_ids = hass.states.async_entity_ids("sensor")
    assert len(running_sensor_ids) > 0
    for running_id in running_sensor_ids:
        sensor = hass.states.get(running_id)
        _LOGGER.info(
            "%s / %s currently %s",
            sensor.attributes.get("sensor_id"),
            sensor.attributes.get("sensor_name"),
            sensor.state,
        )

        sensor_id = sensor.attributes.get("sensor_id")
        sensor_name, sensor_value = EXPECTED_WAVERTREE_SENSOR_RESULTS[sensor_id]
        _LOGGER.info("%s / %s expecting %s", sensor_id, sensor_name, sensor_value)

        assert sensor.state == sensor_value
        assert (
            sensor.attributes.get("last_update").strftime(DATETIME_FORMAT)
            == TEST_DATETIME_STRING
        )
        assert sensor.attributes.get("site_id") == "354107"
        assert sensor.attributes.get("site_name") == TEST_SITE_NAME_WAVERTREE
        assert sensor.attributes.get("attribution") == ATTRIBUTION


@patch("datetime.datetime", MockDateTime)
async def test_two_sensor_sites_running_3hourly(hass, requests_mock):
    """Test we handle two sets of sensors running for two different sites."""

    # all metoffice test data encapsulated in here
    mock_json = json.loads(load_fixture("metoffice.json"))
    all_sites = json.dumps(mock_json["all_sites"])
    wavertree_hourly = json.dumps(mock_json["wavertree_hourly"])
    kingslynn_hourly = json.dumps(mock_json["kingslynn_hourly"])

    requests_mock.get("/public/data/val/wxfcs/all/json/sitelist/", text=all_sites)
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/354107?res=3hourly", text=wavertree_hourly
    )
    requests_mock.get(
        "/public/data/val/wxfcs/all/json/322380?res=3hourly", text=kingslynn_hourly
    )

    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel

    MockDateTime.now = classmethod(
        lambda *args, **kwargs: datetime(2020, 4, 25, 12, tzinfo=timezone.utc)
    )

    entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_WAVERTREE_3HOURLY,)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    entry2 = MockConfigEntry(domain=DOMAIN, data=CONFIG_KINGSLYNN_3HOURLY,)
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    running_sensor_ids = hass.states.async_entity_ids("sensor")
    assert len(running_sensor_ids) > 0
    for running_id in running_sensor_ids:
        sensor = hass.states.get(running_id)
        _LOGGER.info(
            "%s / %s currently %s",
            sensor.attributes.get("sensor_id"),
            sensor.attributes.get("sensor_name"),
            sensor.state,
        )

        sensor_id = sensor.attributes.get("sensor_id")
        if sensor.attributes.get("site_id") == "354107":
            (
                sensor_name,  # pylint: disable=unused-variable
                sensor_value,
            ) = EXPECTED_WAVERTREE_SENSOR_RESULTS[sensor_id]
            assert sensor.state == sensor_value
            assert (
                sensor.attributes.get("last_update").strftime(DATETIME_FORMAT)
                == TEST_DATETIME_STRING
            )
            assert sensor.attributes.get("sensor_id") == sensor_id
            assert sensor.attributes.get("site_id") == "354107"
            assert sensor.attributes.get("site_name") == TEST_SITE_NAME_WAVERTREE
            assert sensor.attributes.get("attribution") == ATTRIBUTION

        else:
            sensor_name, sensor_value = EXPECTED_KINGSLYNN_SENSOR_RESULTS[sensor_id]
            assert sensor.state == sensor_value
            assert (
                sensor.attributes.get("last_update").strftime(DATETIME_FORMAT)
                == TEST_DATETIME_STRING
            )
            assert sensor.attributes.get("sensor_id") == sensor_id
            assert sensor.attributes.get("site_id") == "322380"
            assert sensor.attributes.get("site_name") == TEST_SITE_NAME_KINGSLYNN
            assert sensor.attributes.get("attribution") == ATTRIBUTION
