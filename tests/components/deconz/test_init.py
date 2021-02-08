"""Test deCONZ component setup process."""

import asyncio
from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.deconz import (
    DeconzGateway,
    async_setup_entry,
    async_unload_entry,
    async_update_group_unique_id,
)
from homeassistant.components.deconz.const import (
    CONF_GROUP_ID_BASE,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.helpers import entity_registry

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.common import MockConfigEntry

ENTRY1_HOST = "1.2.3.4"
ENTRY1_PORT = 80
ENTRY1_API_KEY = "1234567890ABCDEF"
ENTRY1_BRIDGEID = "12345ABC"
ENTRY1_UUID = "456DEF"

ENTRY2_HOST = "2.3.4.5"
ENTRY2_PORT = 80
ENTRY2_API_KEY = "1234567890ABCDEF"
ENTRY2_BRIDGEID = "23456DEF"
ENTRY2_UUID = "789ACE"


async def setup_entry(hass, entry):
    """Test that setup entry works."""
    with patch.object(DeconzGateway, "async_setup", return_value=True), patch.object(
        DeconzGateway, "async_update_device_registry", return_value=True
    ):
        assert await async_setup_entry(hass, entry) is True


async def test_setup_entry_fails(hass):
    """Test setup entry fails if deCONZ is not available."""
    with patch("pydeconz.DeconzSession.initialize", side_effect=Exception):
        await setup_deconz_integration(hass)
    assert not hass.data[DECONZ_DOMAIN]


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    with patch("pydeconz.DeconzSession.initialize", side_effect=asyncio.TimeoutError):
        await setup_deconz_integration(hass)
    assert not hass.data[DECONZ_DOMAIN]


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert hass.data[DECONZ_DOMAIN]
    assert gateway.bridgeid in hass.data[DECONZ_DOMAIN]
    assert hass.data[DECONZ_DOMAIN][gateway.bridgeid].master


async def test_setup_entry_multiple_gateways(hass):
    """Test setup entry is successful with multiple gateways."""
    config_entry = await setup_deconz_integration(hass)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    data = deepcopy(DECONZ_WEB_REQUEST)
    data["config"]["bridgeid"] = "01234E56789B"
    config_entry2 = await setup_deconz_integration(
        hass, get_state_response=data, entry_id="2", unique_id="01234E56789B"
    )
    gateway2 = get_gateway_from_config_entry(hass, config_entry2)

    assert len(hass.data[DECONZ_DOMAIN]) == 2
    assert hass.data[DECONZ_DOMAIN][gateway.bridgeid].master
    assert not hass.data[DECONZ_DOMAIN][gateway2.bridgeid].master


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    config_entry = await setup_deconz_integration(hass)
    assert hass.data[DECONZ_DOMAIN]

    assert await async_unload_entry(hass, config_entry)
    assert not hass.data[DECONZ_DOMAIN]


async def test_unload_entry_multiple_gateways(hass):
    """Test being able to unload an entry and master gateway gets moved."""
    config_entry = await setup_deconz_integration(hass)

    data = deepcopy(DECONZ_WEB_REQUEST)
    data["config"]["bridgeid"] = "01234E56789B"
    config_entry2 = await setup_deconz_integration(
        hass, get_state_response=data, entry_id="2", unique_id="01234E56789B"
    )
    gateway2 = get_gateway_from_config_entry(hass, config_entry2)

    assert len(hass.data[DECONZ_DOMAIN]) == 2

    assert await async_unload_entry(hass, config_entry)

    assert len(hass.data[DECONZ_DOMAIN]) == 1
    assert hass.data[DECONZ_DOMAIN][gateway2.bridgeid].master


async def test_update_group_unique_id(hass):
    """Test successful migration of entry data."""
    old_unique_id = "123"
    new_unique_id = "1234"
    entry = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        unique_id=new_unique_id,
        data={
            CONF_API_KEY: "1",
            CONF_HOST: "2",
            CONF_GROUP_ID_BASE: old_unique_id,
            CONF_PORT: "3",
        },
    )

    registry = await entity_registry.async_get_registry(hass)
    # Create entity entry to migrate to new unique ID
    registry.async_get_or_create(
        LIGHT_DOMAIN,
        DECONZ_DOMAIN,
        f"{old_unique_id}-OLD",
        suggested_object_id="old",
        config_entry=entry,
    )
    # Create entity entry with new unique ID
    registry.async_get_or_create(
        LIGHT_DOMAIN,
        DECONZ_DOMAIN,
        f"{new_unique_id}-NEW",
        suggested_object_id="new",
        config_entry=entry,
    )

    await async_update_group_unique_id(hass, entry)

    assert entry.data == {CONF_API_KEY: "1", CONF_HOST: "2", CONF_PORT: "3"}

    old_entity = registry.async_get(f"{LIGHT_DOMAIN}.old")
    assert old_entity.unique_id == f"{new_unique_id}-OLD"

    new_entity = registry.async_get(f"{LIGHT_DOMAIN}.new")
    assert new_entity.unique_id == f"{new_unique_id}-NEW"


async def test_update_group_unique_id_no_legacy_group_id(hass):
    """Test migration doesn't trigger without old legacy group id in entry data."""
    old_unique_id = "123"
    new_unique_id = "1234"
    entry = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        unique_id=new_unique_id,
        data={},
    )

    registry = await entity_registry.async_get_registry(hass)
    # Create entity entry to migrate to new unique ID
    registry.async_get_or_create(
        LIGHT_DOMAIN,
        DECONZ_DOMAIN,
        f"{old_unique_id}-OLD",
        suggested_object_id="old",
        config_entry=entry,
    )

    await async_update_group_unique_id(hass, entry)

    old_entity = registry.async_get(f"{LIGHT_DOMAIN}.old")
    assert old_entity.unique_id == f"{old_unique_id}-OLD"
