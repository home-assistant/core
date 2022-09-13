"""Tests for the Risco binary sensors."""
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .util import TEST_SITE_UUID, zone_mock

FIRST_ENTITY_ID = "binary_sensor.zone_0"
SECOND_ENTITY_ID = "binary_sensor.zone_1"


@pytest.fixture
def two_zone_local():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: zone_mock(), 1: zone_mock()}
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch(
        "homeassistant.components.risco.RiscoLocal.partitions",
        new_callable=PropertyMock(return_value={}),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ):
        yield zone_mocks


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_login(hass, login_with_error, cloud_config_entry):
    """Test error on login."""
    await hass.config_entries.async_setup(cloud_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_cloud_setup(hass, two_zone_cloud, setup_risco_cloud):
    """Test entity setup."""
    registry = er.async_get(hass)
    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)

    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_0")})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_1")})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_cloud_state(hass, zones, triggered, bypassed, entity_id, zone_id):
    with patch.object(
        zones[zone_id],
        "triggered",
        new_callable=PropertyMock(return_value=triggered),
    ), patch.object(
        zones[zone_id],
        "bypassed",
        new_callable=PropertyMock(return_value=bypassed),
    ):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        expected_triggered = STATE_ON if triggered else STATE_OFF
        assert hass.states.get(entity_id).state == expected_triggered
        assert hass.states.get(entity_id).attributes["bypassed"] == bypassed
        assert hass.states.get(entity_id).attributes["zone_id"] == zone_id


async def test_cloud_states(hass, two_zone_cloud, setup_risco_cloud):
    """Test the various alarm states."""
    await _check_cloud_state(hass, two_zone_cloud, True, True, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, True, False, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, False, True, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, False, False, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, True, True, SECOND_ENTITY_ID, 1)
    await _check_cloud_state(hass, two_zone_cloud, True, False, SECOND_ENTITY_ID, 1)
    await _check_cloud_state(hass, two_zone_cloud, False, True, SECOND_ENTITY_ID, 1)
    await _check_cloud_state(hass, two_zone_cloud, False, False, SECOND_ENTITY_ID, 1)


async def test_cloud_bypass(hass, two_zone_cloud, setup_risco_cloud):
    """Test bypassing a zone."""
    with patch("homeassistant.components.risco.RiscoCloud.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "bypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, True)


async def test_cloud_unbypass(hass, two_zone_cloud, setup_risco_cloud):
    """Test unbypassing a zone."""
    with patch("homeassistant.components.risco.RiscoCloud.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "unbypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, False)


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_connect(hass, connect_with_error, local_config_entry):
    """Test error on connect."""
    await hass.config_entries.async_setup(local_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_local_setup(hass, two_zone_local, setup_risco_local):
    """Test entity setup."""
    registry = er.async_get(hass)
    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)

    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_0_local")})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_1_local")})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_local_state(
    hass, zones, triggered, bypassed, entity_id, zone_id, callback
):
    with patch.object(
        zones[zone_id],
        "triggered",
        new_callable=PropertyMock(return_value=triggered),
    ), patch.object(
        zones[zone_id],
        "bypassed",
        new_callable=PropertyMock(return_value=bypassed),
    ):
        await callback(zone_id, zones[zone_id])

        expected_triggered = STATE_ON if triggered else STATE_OFF
        assert hass.states.get(entity_id).state == expected_triggered
        assert hass.states.get(entity_id).attributes["bypassed"] == bypassed
        assert hass.states.get(entity_id).attributes["zone_id"] == zone_id


@pytest.fixture
def _mock_zone_handler():
    with patch("homeassistant.components.risco.RiscoLocal.add_zone_handler") as mock:
        yield mock


async def test_local_states(
    hass, two_zone_local, _mock_zone_handler, setup_risco_local
):
    """Test the various alarm states."""
    callback = _mock_zone_handler.call_args.args[0]

    assert callback is not None

    await _check_local_state(
        hass, two_zone_local, True, True, FIRST_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, True, False, FIRST_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, False, True, FIRST_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, False, False, FIRST_ENTITY_ID, 0, callback
    )
    await _check_local_state(
        hass, two_zone_local, True, True, SECOND_ENTITY_ID, 1, callback
    )
    await _check_local_state(
        hass, two_zone_local, True, False, SECOND_ENTITY_ID, 1, callback
    )
    await _check_local_state(
        hass, two_zone_local, False, True, SECOND_ENTITY_ID, 1, callback
    )
    await _check_local_state(
        hass, two_zone_local, False, False, SECOND_ENTITY_ID, 1, callback
    )


async def test_local_bypass(hass, two_zone_local, setup_risco_local):
    """Test bypassing a zone."""
    with patch.object(two_zone_local[0], "bypass") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "bypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(True)


async def test_local_unbypass(hass, two_zone_local, setup_risco_local):
    """Test unbypassing a zone."""
    with patch.object(two_zone_local[0], "bypass") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "unbypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(False)
