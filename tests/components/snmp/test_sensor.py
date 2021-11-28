"""The test for the SNMP sensor platform."""

import pytest

from homeassistant.components.snmp import DOMAIN


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
async def test_basic(hass, start_ha):
    """Test that we can reload."""
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
                "value_template": "{{ int(value) * 100 }}",
            },
        },
    ],
)
@pytest.mark.parametrize("get_value", [{"1.3.6.1.4.1.3808.1.1.1.4.2.5.0": "1"}])
async def test_template(hass, start_ha):
    """Test that we can reload."""
    assert hass.states.get("sensor.test_oid").state == "100"
