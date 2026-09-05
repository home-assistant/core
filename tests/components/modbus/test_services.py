"""Tests for the Modbus services."""

from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.modbus.const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_VALUE,
    DATA_MODBUS_HUBS,
    DEFAULT_HUB,
    DOMAIN,
    SERVICE_STOP,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)
from homeassistant.const import (
    ATTR_STATE,
    CONF_ADDRESS,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_TYPE,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path

SERVICES = (
    SERVICE_WRITE_REGISTER,
    SERVICE_WRITE_COIL,
    SERVICE_STOP,
    SERVICE_RELOAD,
)

HUB_CONFIG = {
    DOMAIN: [
        {
            CONF_NAME: DEFAULT_HUB,
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusHost",
            CONF_PORT: 5501,
            CONF_SENSORS: [{CONF_NAME: "dummy", CONF_ADDRESS: 9999}],
        }
    ]
}

# The actions that need a working hub, and a minimal valid payload for each.
HUB_SERVICES = [
    pytest.param(
        SERVICE_WRITE_REGISTER,
        {ATTR_HUB: DEFAULT_HUB, ATTR_ADDRESS: 1, ATTR_VALUE: 1},
        id="write_register",
    ),
    pytest.param(
        SERVICE_WRITE_COIL,
        {ATTR_HUB: DEFAULT_HUB, ATTR_ADDRESS: 1, ATTR_STATE: True},
        id="write_coil",
    ),
    pytest.param(SERVICE_STOP, {ATTR_HUB: DEFAULT_HUB}, id="stop"),
]


async def test_services_registered(hass: HomeAssistant) -> None:
    """Test the actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()

    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_without_hubs_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise when Modbus is configured without any hub."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()

    assert hass.data[DATA_MODBUS_HUBS] == {}

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_loaded"
    assert "Modbus is not loaded" in str(err.value)


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_after_failed_setup_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise after a failed hub setup.

    async_modbus_setup stores each hub before awaiting its setup, so a failure
    must drop them again; calling stop on such a hub would otherwise raise
    AttributeError on the never created _connect_task.
    """
    with patch(
        "homeassistant.components.modbus.modbus.ModbusHub.async_setup",
        return_value=False,
    ):
        assert not await async_setup_component(hass, DOMAIN, HUB_CONFIG)
        await hass.async_block_till_done()

    assert DATA_MODBUS_HUBS not in hass.data

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_key == "not_loaded"


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_without_yaml_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions are registered and raise without a Modbus YAML section."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, service)
    assert DATA_MODBUS_HUBS not in hass.data

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_key == "not_loaded"


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_after_failed_reload_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise after a reload left partially set up hubs behind."""
    assert await async_setup_component(hass, DOMAIN, HUB_CONFIG)
    await hass.async_block_till_done()
    assert hass.data[DATA_MODBUS_HUBS]

    yaml_path = get_fixture_path("configuration.yaml", DOMAIN)
    with (
        patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path),
        patch(
            "homeassistant.components.modbus.modbus.ModbusHub.async_setup",
            return_value=False,
        ),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_key == "not_loaded"
