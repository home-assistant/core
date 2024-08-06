"""Tests for the Risco binary sensors."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .util import TEST_SITE_NAME, TEST_SITE_UUID, system_mock

FIRST_ENTITY_ID = "binary_sensor.zone_0"
SECOND_ENTITY_ID = "binary_sensor.zone_1"
FIRST_ALARMED_ENTITY_ID = FIRST_ENTITY_ID + "_alarmed"
SECOND_ALARMED_ENTITY_ID = SECOND_ENTITY_ID + "_alarmed"
FIRST_ARMED_ENTITY_ID = FIRST_ENTITY_ID + "_armed"
SECOND_ARMED_ENTITY_ID = SECOND_ENTITY_ID + "_armed"


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_login(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    login_with_error,
    cloud_config_entry,
) -> None:
    """Test error on login."""
    await hass.config_entries.async_setup(cloud_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(FIRST_ENTITY_ID)
    assert not entity_registry.async_is_registered(SECOND_ENTITY_ID)


async def test_cloud_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    two_zone_cloud,
    setup_risco_cloud,
) -> None:
    """Test entity setup."""
    assert entity_registry.async_is_registered(FIRST_ENTITY_ID)
    assert entity_registry.async_is_registered(SECOND_ENTITY_ID)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SITE_UUID + "_zone_0")}
    )
    assert device is not None
    assert device.manufacturer == "Risco"

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SITE_UUID + "_zone_1")}
    )
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_cloud_state(hass, zones, triggered, entity_id, zone_id):
    with patch.object(
        zones[zone_id],
        "triggered",
        new_callable=PropertyMock(return_value=triggered),
    ):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        expected_triggered = STATE_ON if triggered else STATE_OFF
        assert hass.states.get(entity_id).state == expected_triggered
        assert hass.states.get(entity_id).attributes["zone_id"] == zone_id


async def test_cloud_states(
    hass: HomeAssistant, two_zone_cloud, setup_risco_cloud
) -> None:
    """Test the various alarm states."""
    await _check_cloud_state(hass, two_zone_cloud, True, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, False, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, True, SECOND_ENTITY_ID, 1)
    await _check_cloud_state(hass, two_zone_cloud, False, SECOND_ENTITY_ID, 1)


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_connect(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    connect_with_error,
    local_config_entry,
) -> None:
    """Test error on connect."""
    await hass.config_entries.async_setup(local_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(FIRST_ENTITY_ID)
    assert not entity_registry.async_is_registered(SECOND_ENTITY_ID)
    assert not entity_registry.async_is_registered(FIRST_ALARMED_ENTITY_ID)
    assert not entity_registry.async_is_registered(SECOND_ALARMED_ENTITY_ID)


async def test_local_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    two_zone_local,
    setup_risco_local,
) -> None:
    """Test entity setup."""
    assert entity_registry.async_is_registered(FIRST_ENTITY_ID)
    assert entity_registry.async_is_registered(SECOND_ENTITY_ID)
    assert entity_registry.async_is_registered(FIRST_ALARMED_ENTITY_ID)
    assert entity_registry.async_is_registered(SECOND_ALARMED_ENTITY_ID)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SITE_UUID + "_zone_0_local")}
    )
    assert device is not None
    assert device.manufacturer == "Risco"

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_SITE_UUID + "_zone_1_local")}
    )
    assert device is not None
    assert device.manufacturer == "Risco"

    device = device_registry.async_get_device(identifiers={(DOMAIN, TEST_SITE_UUID)})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_local_state(
    hass, zones, entity_property, value, entity_id, zone_id, callback
):
    with patch.object(
        zones[zone_id],
        entity_property,
        new_callable=PropertyMock(return_value=value),
    ):
        await callback(zone_id, zones[zone_id])
        await hass.async_block_till_done()

        expected_value = STATE_ON if value else STATE_OFF
        assert hass.states.get(entity_id).state == expected_value
        assert hass.states.get(entity_id).attributes["zone_id"] == zone_id


@pytest.fixture
def mock_zone_handler():
    """Create a mock for add_zone_handler."""
    with patch("homeassistant.components.risco.RiscoLocal.add_zone_handler") as mock:
        yield mock


async def test_local_states(
    hass: HomeAssistant, two_zone_local, mock_zone_handler, setup_risco_local
) -> None:
    """Test the various zone states."""
    callback = mock_zone_handler.call_args.args[0]

    assert callback is not None

    await _check_local_state(
        hass, two_zone_local, "triggered", True, FIRST_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, "triggered", False, FIRST_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, "triggered", True, SECOND_ENTITY_ID, 1, callback
    )
    await _check_local_state(
        hass, two_zone_local, "triggered", False, SECOND_ENTITY_ID, 1, callback
    )


async def test_alarmed_local_states(
    hass: HomeAssistant, two_zone_local, mock_zone_handler, setup_risco_local
) -> None:
    """Test the various zone alarmed states."""
    callback = mock_zone_handler.call_args.args[0]

    assert callback is not None

    await _check_local_state(
        hass, two_zone_local, "alarmed", True, FIRST_ALARMED_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, "alarmed", False, FIRST_ALARMED_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, "alarmed", True, SECOND_ALARMED_ENTITY_ID, 1, callback
    )
    await _check_local_state(
        hass, two_zone_local, "alarmed", False, SECOND_ALARMED_ENTITY_ID, 1, callback
    )


async def test_armed_local_states(
    hass: HomeAssistant, two_zone_local, mock_zone_handler, setup_risco_local
) -> None:
    """Test the various zone armed states."""
    callback = mock_zone_handler.call_args.args[0]

    assert callback is not None

    await _check_local_state(
        hass, two_zone_local, "armed", True, FIRST_ARMED_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, "armed", False, FIRST_ARMED_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, "armed", True, SECOND_ARMED_ENTITY_ID, 1, callback
    )
    await _check_local_state(
        hass, two_zone_local, "armed", False, SECOND_ARMED_ENTITY_ID, 1, callback
    )


async def _check_system_state(hass, system, entity_property, value, callback):
    with patch.object(
        system,
        entity_property,
        new_callable=PropertyMock(return_value=value),
    ):
        await callback(system)
        await hass.async_block_till_done()

        expected_value = STATE_ON if value else STATE_OFF
        if entity_property == "ac_trouble":
            entity_property = "a_c_trouble"
        entity_id = f"binary_sensor.test_site_name_{entity_property}"
        assert hass.states.get(entity_id).state == expected_value


@pytest.fixture
def mock_system_handler():
    """Create a mock for add_system_handler."""
    with patch("homeassistant.components.risco.RiscoLocal.add_system_handler") as mock:
        yield mock


@pytest.fixture
def system_only_local():
    """Fixture to mock a system with no zones or partitions."""
    system = system_mock()
    with (
        patch.object(
            system, "name", new_callable=PropertyMock(return_value=TEST_SITE_NAME)
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.zones",
            new_callable=PropertyMock(return_value={}),
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.partitions",
            new_callable=PropertyMock(return_value={}),
        ),
        patch(
            "homeassistant.components.risco.RiscoLocal.system",
            new_callable=PropertyMock(return_value=system),
        ),
    ):
        yield system


async def test_system_states(
    hass: HomeAssistant, system_only_local, mock_system_handler, setup_risco_local
) -> None:
    """Test the various zone states."""
    callback = mock_system_handler.call_args.args[0]

    assert callback is not None

    properties = [
        "low_battery_trouble",
        "ac_trouble",
        "monitoring_station_1_trouble",
        "monitoring_station_2_trouble",
        "monitoring_station_3_trouble",
        "phone_line_trouble",
        "clock_trouble",
        "box_tamper",
    ]
    for entity_property in properties:
        await _check_system_state(
            hass, system_only_local, entity_property, True, callback
        )
        await _check_system_state(
            hass, system_only_local, entity_property, False, callback
        )
