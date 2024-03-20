"""Tests for the Risco binary sensors."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

FIRST_ENTITY_ID = "switch.zone_0_bypassed"
SECOND_ENTITY_ID = "switch.zone_1_bypassed"


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_login(
    hass: HomeAssistant, login_with_error, cloud_config_entry
) -> None:
    """Test error on login."""
    await hass.config_entries.async_setup(cloud_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_cloud_setup(
    hass: HomeAssistant, two_zone_cloud, setup_risco_cloud
) -> None:
    """Test entity setup."""
    registry = er.async_get(hass)
    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)


async def _check_cloud_state(hass, zones, bypassed, entity_id, zone_id):
    with patch.object(
        zones[zone_id],
        "bypassed",
        new_callable=PropertyMock(return_value=bypassed),
    ):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        expected_bypassed = STATE_ON if bypassed else STATE_OFF
        assert hass.states.get(entity_id).state == expected_bypassed
        assert hass.states.get(entity_id).attributes["zone_id"] == zone_id


async def test_cloud_states(
    hass: HomeAssistant, two_zone_cloud, setup_risco_cloud
) -> None:
    """Test the various alarm states."""
    await _check_cloud_state(hass, two_zone_cloud, True, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, False, FIRST_ENTITY_ID, 0)
    await _check_cloud_state(hass, two_zone_cloud, True, SECOND_ENTITY_ID, 1)
    await _check_cloud_state(hass, two_zone_cloud, False, SECOND_ENTITY_ID, 1)


async def test_cloud_bypass(
    hass: HomeAssistant, two_zone_cloud, setup_risco_cloud
) -> None:
    """Test bypassing a zone."""
    with patch("homeassistant.components.risco.RiscoCloud.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, True)


async def test_cloud_unbypass(
    hass: HomeAssistant, two_zone_cloud, setup_risco_cloud
) -> None:
    """Test unbypassing a zone."""
    with patch("homeassistant.components.risco.RiscoCloud.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, False)


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_connect(
    hass: HomeAssistant, connect_with_error, local_config_entry
) -> None:
    """Test error on connect."""
    await hass.config_entries.async_setup(local_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_local_setup(
    hass: HomeAssistant, two_zone_local, setup_risco_local
) -> None:
    """Test entity setup."""
    registry = er.async_get(hass)
    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)


async def _check_local_state(hass, zones, bypassed, entity_id, zone_id, callback):
    with patch.object(
        zones[zone_id],
        "bypassed",
        new_callable=PropertyMock(return_value=bypassed),
    ):
        await callback(zone_id, zones[zone_id])
        await hass.async_block_till_done()

        expected_bypassed = STATE_ON if bypassed else STATE_OFF
        assert hass.states.get(entity_id).state == expected_bypassed
        assert hass.states.get(entity_id).attributes["zone_id"] == zone_id


@pytest.fixture
def mock_zone_handler():
    """Create a mock for add_zone_handler."""
    with patch("homeassistant.components.risco.RiscoLocal.add_zone_handler") as mock:
        yield mock


async def test_local_states(
    hass: HomeAssistant, two_zone_local, mock_zone_handler, setup_risco_local
) -> None:
    """Test the various alarm states."""
    callback = mock_zone_handler.call_args.args[0]

    assert callback is not None

    await _check_local_state(hass, two_zone_local, True, FIRST_ENTITY_ID, 0, callback)
    await _check_local_state(hass, two_zone_local, False, FIRST_ENTITY_ID, 0, callback)
    await _check_local_state(hass, two_zone_local, True, SECOND_ENTITY_ID, 1, callback)
    await _check_local_state(hass, two_zone_local, False, SECOND_ENTITY_ID, 1, callback)


async def test_local_bypass(
    hass: HomeAssistant, two_zone_local, setup_risco_local
) -> None:
    """Test bypassing a zone."""
    with patch.object(two_zone_local[0], "bypass") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(True)


async def test_local_unbypass(
    hass: HomeAssistant, two_zone_local, setup_risco_local
) -> None:
    """Test unbypassing a zone."""
    with patch.object(two_zone_local[0], "bypass") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(False)
