"""Tests for rest component."""

import asyncio
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import respx

from homeassistant import config as hass_config
from homeassistant.components.rest.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    get_fixture_path,
)


@respx.mock
async def test_setup_with_endpoint_timeout_with_recovery(hass: HomeAssistant) -> None:
    """Test setup with an endpoint that times out that recovers."""
    await async_setup_component(hass, "homeassistant", {})

    respx.get("http://localhost").mock(side_effect=asyncio.TimeoutError())
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "method": "GET",
                    "verify_ssl": "false",
                    "timeout": 30,
                    "sensor": [
                        {
                            "unit_of_measurement": UnitOfInformation.MEGABYTES,
                            "name": "sensor1",
                            "value_template": "{{ value_json.sensor1 }}",
                        },
                        {
                            "unit_of_measurement": UnitOfInformation.MEGABYTES,
                            "name": "sensor2",
                            "value_template": "{{ value_json.sensor2 }}",
                        },
                    ],
                    "binary_sensor": [
                        {
                            "name": "binary_sensor1",
                            "value_template": "{{ value_json.binary_sensor1 }}",
                        },
                        {
                            "name": "binary_sensor2",
                            "value_template": "{{ value_json.binary_sensor2 }}",
                        },
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        json={
            "sensor1": "1",
            "sensor2": "2",
            "binary_sensor1": "on",
            "binary_sensor2": "off",
        },
    )

    # Refresh the coordinator
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    # Wait for platform setup retry
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 4

    assert hass.states.get("sensor.sensor1").state == "1"
    assert hass.states.get("sensor.sensor2").state == "2"
    assert hass.states.get("binary_sensor.binary_sensor1").state == "on"
    assert hass.states.get("binary_sensor.binary_sensor2").state == "off"

    # Now the end point flakes out again
    respx.get("http://localhost").mock(side_effect=asyncio.TimeoutError())

    # Refresh the coordinator
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sensor1").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.sensor2").state == STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.binary_sensor1").state == STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.binary_sensor2").state == STATE_UNAVAILABLE

    # We request a manual refresh when the
    # endpoint is working again

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        json={
            "sensor1": "1",
            "sensor2": "2",
            "binary_sensor1": "on",
            "binary_sensor2": "off",
        },
    )

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.sensor1"]},
        blocking=True,
    )
    assert hass.states.get("sensor.sensor1").state == "1"
    assert hass.states.get("sensor.sensor2").state == "2"
    assert hass.states.get("binary_sensor.binary_sensor1").state == "on"
    assert hass.states.get("binary_sensor.binary_sensor2").state == "off"


@respx.mock
async def test_setup_minimum_resource_template(hass: HomeAssistant) -> None:
    """Test setup with minimum configuration (resource_template)."""

    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        json={
            "sensor1": "1",
            "sensor2": "2",
            "binary_sensor1": "on",
            "binary_sensor2": "off",
        },
    )
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource_template": "{% set url = 'http://localhost' %}{{ url }}",
                    "method": "GET",
                    "verify_ssl": "false",
                    "timeout": 30,
                    "sensor": [
                        {
                            "unit_of_measurement": UnitOfInformation.MEGABYTES,
                            "name": "sensor1",
                            "value_template": "{{ value_json.sensor1 }}",
                        },
                        {
                            "unit_of_measurement": UnitOfInformation.MEGABYTES,
                            "name": "sensor2",
                            "value_template": "{{ value_json.sensor2 }}",
                        },
                    ],
                    "binary_sensor": [
                        {
                            "name": "binary_sensor1",
                            "value_template": "{{ value_json.binary_sensor1 }}",
                        },
                        {
                            "name": "binary_sensor2",
                            "value_template": "{{ value_json.binary_sensor2 }}",
                        },
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4

    assert hass.states.get("sensor.sensor1").state == "1"
    assert hass.states.get("sensor.sensor2").state == "2"
    assert hass.states.get("binary_sensor.binary_sensor1").state == "on"
    assert hass.states.get("binary_sensor.binary_sensor2").state == "off"


@respx.mock
async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload."""

    respx.get("http://localhost") % HTTPStatus.OK

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "method": "GET",
                    "verify_ssl": "false",
                    "timeout": 30,
                    "sensor": [
                        {
                            "name": "mockrest",
                        },
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("sensor.mockrest")

    yaml_path = get_fixture_path("configuration_top_level.yaml", "rest")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "rest",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.mockreset") is None
    assert hass.states.get("sensor.rollout")
    assert hass.states.get("sensor.fallover")


@respx.mock
async def test_reload_and_remove_all(hass: HomeAssistant) -> None:
    """Verify we can reload and remove all."""

    respx.get("http://localhost") % HTTPStatus.OK

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "method": "GET",
                    "verify_ssl": "false",
                    "timeout": 30,
                    "sensor": [
                        {
                            "name": "mockrest",
                        },
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("sensor.mockrest")

    yaml_path = get_fixture_path("configuration_empty.yaml", "rest")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "rest",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.mockreset") is None


@respx.mock
async def test_reload_fails_to_read_configuration(hass: HomeAssistant) -> None:
    """Verify reload when configuration is missing or broken."""

    respx.get("http://localhost") % HTTPStatus.OK

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://localhost",
                    "method": "GET",
                    "verify_ssl": "false",
                    "timeout": 30,
                    "sensor": [
                        {
                            "name": "mockrest",
                        },
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    yaml_path = get_fixture_path("configuration_invalid.notyaml", "rest")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "rest",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1


@respx.mock
async def test_multiple_rest_endpoints(hass: HomeAssistant) -> None:
    """Test multiple rest endpoints."""

    respx.get("http://date.jsontest.com").respond(
        status_code=HTTPStatus.OK,
        json={
            "date": "03-17-2021",
            "milliseconds_since_epoch": 1616008268573,
            "time": "07:11:08 PM",
        },
    )

    respx.get("http://time.jsontest.com").respond(
        status_code=HTTPStatus.OK,
        json={
            "date": "03-17-2021",
            "milliseconds_since_epoch": 1616008299665,
            "time": "07:11:39 PM",
        },
    )
    respx.get("http://localhost").respond(
        status_code=HTTPStatus.OK,
        json={
            "value": "1",
        },
    )
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "resource": "http://date.jsontest.com",
                    "sensor": [
                        {
                            "name": "JSON Date",
                            "value_template": "{{ value_json.date }}",
                        },
                        {
                            "name": "JSON Date Time",
                            "value_template": "{{ value_json.time }}",
                        },
                    ],
                },
                {
                    "resource": "http://time.jsontest.com",
                    "sensor": [
                        {
                            "name": "JSON Time",
                            "value_template": "{{ value_json.time }}",
                        },
                    ],
                },
                {
                    "resource": "http://localhost",
                    "binary_sensor": [
                        {
                            "name": "Binary Sensor",
                            "value_template": "{{ value_json.value }}",
                        },
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4

    assert hass.states.get("sensor.json_date").state == "03-17-2021"
    assert hass.states.get("sensor.json_date_time").state == "07:11:08 PM"
    assert hass.states.get("sensor.json_time").state == "07:11:39 PM"
    assert hass.states.get("binary_sensor.binary_sensor").state == "on"


async def test_empty_config(hass: HomeAssistant) -> None:
    """Test setup with empty configuration.

    For example (with rest.yaml an empty file):
        rest: !include rest.yaml
    """
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {}},
    )
    assert_setup_component(0, DOMAIN)


async def test_config_schema_via_packages(hass: HomeAssistant) -> None:
    """Test configuration via packages."""
    packages = {
        "pack_dict": {"rest": {}},
        "pack_11": {"rest": {"resource": "http://url1"}},
        "pack_list": {"rest": [{"resource": "http://url2"}]},
    }
    config = {hass_config.CONF_CORE: {hass_config.CONF_PACKAGES: packages}}
    await hass_config.merge_packages_config(hass, config, packages)

    assert len(config) == 2
    assert len(config["rest"]) == 2
    assert config["rest"][0]["resource"] == "http://url1"
    assert config["rest"][1]["resource"] == "http://url2"
