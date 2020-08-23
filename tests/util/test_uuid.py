"""Test Home Assistant uuid util methods."""

import uuid

import homeassistant.util.uuid as uuid_util


async def test_uuid_v1mc_hex():
    """Verify we can generate a uuid_v1mc and return hex."""
    assert len(uuid_util.uuid_v1mc_hex()) == 32
    assert uuid.UUID(uuid_util.uuid_v1mc_hex())
