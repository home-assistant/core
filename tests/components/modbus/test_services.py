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
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path

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

SERVICES = (
    SERVICE_RELOAD,
    SERVICE_WRITE_REGISTER,
    SERVICE_WRITE_COIL,
    SERVICE_STOP,
)

# The actions that need a configured hub, and a minimal valid payload for each.
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


@pytest.mark.parametrize("service", SERVICES)
async def test_services_registered_without_yaml(
    hass: HomeAssistant, service: str
) -> None:
    """Test the actions are registered without a Modbus YAML section."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_without_yaml_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the hub actions raise without a Modbus YAML section."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert DATA_MODBUS_HUBS not in hass.data

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_loaded"
    assert "Modbus is not loaded" in str(err.value)


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_without_hubs_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the hub actions raise when Modbus is configured without any hub."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()

    assert hass.data[DATA_MODBUS_HUBS] == {}

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_key == "not_loaded"


@pytest.mark.parametrize(("service", "data"), HUB_SERVICES)
async def test_service_after_failed_setup_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the hub actions raise after a failed hub setup.

    Hubs are stored before their setup is awaited, so a failure must drop them
    again; stop would otherwise raise AttributeError on the unset _connect_task.
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
async def test_service_after_failed_reload_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the hub actions raise after a reload failed to set the hubs up."""
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

    assert DATA_MODBUS_HUBS not in hass.data

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_key == "not_loaded"


TEST_HUB_A = "hub_a"
TEST_HUB_B = "hub_b"


def _two_hub_config() -> dict:
    """Return a config with two hubs, each exposing one sensor."""
    return {
        DOMAIN: [
            {
                CONF_NAME: name,
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusHost",
                CONF_PORT: port,
                CONF_SENSORS: [{CONF_NAME: f"sensor_{name}", CONF_ADDRESS: 1}],
            }
            for name, port in ((TEST_HUB_A, 5501), (TEST_HUB_B, 5502))
        ]
    }


@pytest.mark.usefixtures("mock_pymodbus")
async def test_stop_only_disables_the_selected_hub(hass: HomeAssistant) -> None:
    """Test stopping one hub leaves the other hub's entities alone."""
    assert await async_setup_component(hass, DOMAIN, _two_hub_config())
    await hass.async_block_till_done()

    # async_disable only flips availability, it does not write the state, so the
    # entity objects rather than the state machine show the effect.
    entities = {
        entity.entity_id: entity
        for platform in async_get_platforms(hass, DOMAIN)
        for entity in platform.entities.values()
    }
    entity_a = entities[f"sensor.sensor_{TEST_HUB_A}"]
    entity_b = entities[f"sensor.sensor_{TEST_HUB_B}"]
    assert entity_a.available
    assert entity_b.available

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP, {ATTR_HUB: TEST_HUB_A}, blocking=True
    )
    await hass.async_block_till_done()

    assert not entity_a.available
    assert entity_b.available
