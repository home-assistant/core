"""Tests for the Risco binary sensors."""
from unittest.mock import PropertyMock, patch

from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .util import (  # noqa: F401
    TEST_CLOUD_CONFIG,
    TEST_LOCAL_CONFIG,
    TEST_SITE_UUID,
    setup_risco_cloud,
    setup_risco_local,
    two_zone_cloud,
    two_zone_local,
)

from tests.common import MockConfigEntry

FIRST_ENTITY_ID = "binary_sensor.zone_0"
SECOND_ENTITY_ID = "binary_sensor.zone_1"


async def test_cloud_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.risco.RiscoCloud.login",
        side_effect=CannotConnectError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CLOUD_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_cloud_unauthorized(hass):
    """Test unauthorized error."""

    with patch(
        "homeassistant.components.risco.RiscoCloud.login",
        side_effect=UnauthorizedError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CLOUD_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_cloud_setup(hass, two_zone_cloud):  # noqa: F811
    """Test entity setup."""
    registry = er.async_get(hass)

    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)

    await setup_risco_cloud(hass)

    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)

    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_0")})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_1")})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_state(hass, zones, triggered, bypassed, entity_id, zone_id):
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


async def test_cloud_states(hass, two_zone_cloud):  # noqa: F811
    """Test the various alarm states."""
    await setup_risco_cloud(hass)

    await _check_state(hass, two_zone_cloud, True, True, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_cloud, True, False, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_cloud, False, True, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_cloud, False, False, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_cloud, True, True, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_cloud, True, False, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_cloud, False, True, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_cloud, False, False, SECOND_ENTITY_ID, 1)


async def test_cloud_bypass(hass, two_zone_cloud):  # noqa: F811
    """Test bypassing a zone."""
    await setup_risco_cloud(hass)
    with patch("homeassistant.components.risco.RiscoCloud.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "bypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, True)


async def test_cloud_unbypass(hass, two_zone_cloud):  # noqa: F811
    """Test unbypassing a zone."""
    await setup_risco_cloud(hass)
    with patch("homeassistant.components.risco.RiscoCloud.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "unbypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, False)


async def test_local_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.risco.RiscoLocal.connect",
        side_effect=CannotConnectError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_LOCAL_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_local_unauthorized(hass):
    """Test unauthorized error."""

    with patch(
        "homeassistant.components.risco.RiscoLocal.connect",
        side_effect=UnauthorizedError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_LOCAL_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_local_setup(hass, two_zone_local):  # noqa: F811
    """Test entity setup."""
    registry = er.async_get(hass)

    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)

    await setup_risco_local(hass)

    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)

    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_0_local")})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_1_local")})
    assert device is not None
    assert device.manufacturer == "Risco"


async def test_local_states(hass, two_zone_local):  # noqa: F811
    """Test the various alarm states."""
    await setup_risco_local(hass)

    await _check_state(hass, two_zone_local, True, True, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_local, True, False, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_local, False, True, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_local, False, False, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_local, True, True, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_local, True, False, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_local, False, True, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_local, False, False, SECOND_ENTITY_ID, 1)


async def test_local_bypass(hass, two_zone_local):  # noqa: F811
    """Test bypassing a zone."""
    await setup_risco_local(hass)
    with patch.object(two_zone_local[0], "bypass") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "bypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(True)


async def test_local_unbypass(hass, two_zone_local):  # noqa: F811
    """Test unbypassing a zone."""
    await setup_risco_local(hass)
    with patch.object(two_zone_local[0], "bypass") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "unbypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(False)
