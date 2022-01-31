"""Tests for the WebOS TV integration."""
from pickle import dumps
from unittest.mock import patch

import sqlalchemy as db
from sqlalchemy import create_engine

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.webostv.const import DOMAIN
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from .const import CLIENT_KEY, FAKE_UUID, HOST, MOCK_CLIENT_KEYS, TV_NAME

from tests.common import MockConfigEntry


async def setup_webostv(hass, unique_id=FAKE_UUID):
    """Initialize webostv and media_player for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_CLIENT_SECRET: CLIENT_KEY,
        },
        title=TV_NAME,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.webostv.read_client_keys",
        return_value=MOCK_CLIENT_KEYS,
    ):
        await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_HOST: HOST}},
        )
        await hass.async_block_till_done()

    return entry


async def setup_legacy_component(hass, create_entity=True):
    """Initialize webostv component with legacy entity."""
    if create_entity:
        ent_reg = entity_registry.async_get(hass)
        assert ent_reg.async_get_or_create(MP_DOMAIN, DOMAIN, CLIENT_KEY)

    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_HOST: HOST}},
    )
    await hass.async_block_till_done()


def create_memory_sqlite_engine(url):
    """Create fake db keys file in memory."""
    mem_eng = create_engine("sqlite:///:memory:")
    table = db.Table(
        "unnamed",
        db.MetaData(),
        db.Column("key", db.String),
        db.Column("value", db.String),
    )
    table.create(mem_eng)
    query = db.insert(table).values(key=HOST, value=dumps(CLIENT_KEY))
    connection = mem_eng.connect()
    connection.execute(query)
    return mem_eng


def is_entity_unique_id_updated(hass):
    """Check if entity has new unique_id from UUID."""
    ent_reg = entity_registry.async_get(hass)
    return ent_reg.async_get_entity_id(
        MP_DOMAIN, DOMAIN, FAKE_UUID
    ) and not ent_reg.async_get_entity_id(MP_DOMAIN, DOMAIN, CLIENT_KEY)
