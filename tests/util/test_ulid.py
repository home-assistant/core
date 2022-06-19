"""Test Home Assistant ulid util methods."""

import uuid

import homeassistant.util.ulid as ulid_util


async def test_ulid_util_uuid_hex():
    """Verify we can generate a ulid in hex."""
    assert len(ulid_util.ulid_hex()) == 32
    assert uuid.UUID(ulid_util.ulid_hex())


async def test_ulid_util_uuid():
    """Verify we can generate a ulid."""
    assert len(ulid_util.ulid()) == 26
