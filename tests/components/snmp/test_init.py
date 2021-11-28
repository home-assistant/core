"""The test for the SNMP sensor platform."""
from unittest.mock import patch

import pytest

from homeassistant import config
from homeassistant.components.snmp import DOMAIN
from homeassistant.helpers.reload import SERVICE_RELOAD

from tests.common import get_fixture_path


@pytest.mark.parametrize("count,domain", [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "name": "Test OID",
                "unit_of_measurement": "kW",
                "baseoid": "1.3.6.1.4.1.3808.1.1.1.4.2.5.0",
                "host": "192.168.210.25",
                "community": "public",
            },
        },
    ],
)
@pytest.mark.parametrize(
    "get_value",
    [{"1.3.6.1.4.1.3808.1.1.1.4.2.5.0": "1", "1.3.6.1.4.1.3808.1.1.1.4.2.5.1": "2"}],
)
async def test_reloadable(hass, start_ha):
    """Test that we can reload."""
    assert hass.states.get("sensor.test_oid").state == "1"
    assert len(hass.states.async_all()) == 1

    await async_yaml_patch_helper(hass, "sensor_configuration.yaml")
    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test_oid").state == "1"
    assert hass.states.get("sensor.other_oid").state == "2"


@pytest.mark.parametrize("count,domain", [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "name": "Test OID",
                "unit_of_measurement": "kW",
                "baseoid": "1.3.6.1.4.1.3808.1.1.1.4.2.5.0",
                "host": "192.168.210.25",
                "community": "public",
            },
        },
    ],
)
@pytest.mark.parametrize("get_value", [{"1.3.6.1.4.1.3808.1.1.1.4.2.5.0": "1"}])
async def test_reloadable_can_remove(hass, start_ha):
    """Test that we can reload and remove all snmp sensors."""
    assert hass.states.get("sensor.test_oid").state == "1"
    # assert hass.states.get("sensor.other_oid").state == "1"

    await async_yaml_patch_helper(hass, "empty_configuration.yaml")
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize("count,domain", [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "name": "Test OID",
                "unit_of_measurement": "kW",
                "baseoid": "1.3.6.1.4.1.3808.1.1.1.4.2.5.1",
                "host": "192.168.210.25",
                "community": "public",
            },
        },
    ],
)
@pytest.mark.parametrize(
    "get_value",
    [{"1.3.6.1.4.1.3808.1.1.1.4.2.5.0": "1", "1.3.6.1.4.1.3808.1.1.1.4.2.5.1": "2"}],
)
async def test_reloadable_can_change_oid(hass, start_ha):
    """Test that we can reload and change the snmp oid configuration."""
    assert hass.states.get("sensor.test_oid").state == "2"
    assert len(hass.states.async_all()) == 1

    await async_yaml_patch_helper(hass, "sensor_configuration.yaml")
    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test_oid").state == "1"
    assert hass.states.get("sensor.other_oid").state == "2"


@pytest.mark.parametrize("count,domain", [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "name": "Test OID",
                "unit_of_measurement": "kW",
                "baseoid": "1.3.6.1.4.1.3808.1.1.1.4.2.5.0",
                "host": "192.168.210.25",
                "community": "public",
            },
        },
    ],
)
@pytest.mark.parametrize("get_value", [{"1.3.6.1.4.1.3808.1.1.1.4.2.5.0": "1"}])
async def test_reloadable_stops_on_invalid_config(hass, start_ha):
    """Test we stop the reload if configuration.yaml is completely broken."""
    assert hass.states.get("sensor.test_oid").state == "1"
    assert len(hass.states.async_all()) == 1

    await async_yaml_patch_helper(hass, "configuration.yaml.corrupt")
    assert hass.states.get("sensor.test_oid").state == "1"
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize("count,domain", [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "name": "Test OID",
                "unit_of_measurement": "kW",
                "baseoid": "1.3.6.1.4.1.3808.1.1.1.4.2.5.0",
                "host": "192.168.210.25",
                "community": "public",
            },
        },
    ],
)
@pytest.mark.parametrize(
    "get_value",
    [{"1.3.6.1.4.1.3808.1.1.1.4.2.5.0": "1", "1.3.6.1.4.1.3808.1.1.1.4.2.5.1": "2"}],
)
async def test_reloadable_handles_partial_valid_config(hass, start_ha):
    """Test we can still setup valid sensors when configuration.yaml has a broken entry."""
    assert hass.states.get("sensor.test_oid").state == "1"
    assert len(hass.states.async_all()) == 1

    await async_yaml_patch_helper(hass, "sensor_configuration.yaml")
    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test_oid").state == "1"
    assert hass.states.get("sensor.other_oid").state == "2"


async def async_yaml_patch_helper(hass, filename):
    """Help update configuration.yaml."""
    yaml_path = get_fixture_path(filename, "snmp")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()
