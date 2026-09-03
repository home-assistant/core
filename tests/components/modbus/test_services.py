"""Tests for the Modbus services."""

from unittest.mock import patch

import pytest

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

SERVICES = (
    SERVICE_WRITE_REGISTER,
    SERVICE_WRITE_COIL,
    SERVICE_STOP,
    SERVICE_RELOAD,
)


async def test_services_registered(hass: HomeAssistant) -> None:
    """Test the actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()

    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(
    ("service", "data"),
    [
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
    ],
)
async def test_service_without_hubs_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise a user-facing error when Modbus is not set up."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()
    hass.data.pop(DATA_MODBUS_HUBS)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_loaded"
    assert "Modbus is not loaded" in str(err.value)


@pytest.mark.parametrize(
    ("service", "data"),
    [
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
    ],
)
async def test_service_after_failed_setup_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise when a failed hub setup left hubs behind.

    async_modbus_setup stores each hub before awaiting its setup, so a failed
    hub leaves DATA_MODBUS_HUBS populated while the component is not loaded.
    Calling stop on such a hub would raise AttributeError on _connect_task.
    """
    with patch(
        "homeassistant.components.modbus.modbus.ModbusHub.async_setup",
        return_value=False,
    ):
        assert not await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {
                        CONF_NAME: DEFAULT_HUB,
                        CONF_TYPE: "tcp",
                        CONF_HOST: "modbusHost",
                        CONF_PORT: 5501,
                        CONF_SENSORS: [{CONF_NAME: "dummy", CONF_ADDRESS: 9999}],
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    # The failed hub is still in hass.data, but the component is not loaded.
    assert hass.data[DATA_MODBUS_HUBS]
    assert DOMAIN not in hass.config.components

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_key == "not_loaded"
