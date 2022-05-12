"""Test Home Assistant uuid util methods."""

import uuid

import homeassistant.util.uuid as uuid_util


async def test_uuid_util_random_uuid_hex():
    """Verify we can generate a random uuid."""
    assert len(uuid_util.random_uuid_hex()) == 32
    assert uuid.UUID(uuid_util.random_uuid_hex())
