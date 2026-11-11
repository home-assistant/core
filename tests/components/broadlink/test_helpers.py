"""Tests for Broadlink helper functions."""

from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.broadlink.const import (
    CONF_ENTRY_KIND,
    DOMAIN,
    ENTRY_KIND_MAGIC_FAMILY,
)
from homeassistant.components.broadlink.helpers import (
    data_packet,
    import_device,
    mac_address,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant


async def test_padding(hass: HomeAssistant) -> None:
    """Verify that non padding strings are allowed."""
    assert data_packet("Jg") == b"&"
    assert data_packet("Jg=") == b"&"
    assert data_packet("Jg==") == b"&"


async def test_valid_mac_address(hass: HomeAssistant) -> None:
    """Test we convert a valid MAC address to bytes."""
    valid = [
        "A1B2C3D4E5F6",
        "a1b2c3d4e5f6",
        "A1B2-C3D4-E5F6",
        "a1b2-c3d4-e5f6",
        "A1B2.C3D4.E5F6",
        "a1b2.c3d4.e5f6",
        "A1-B2-C3-D4-E5-F6",
        "a1-b2-c3-d4-e5-f6",
        "A1:B2:C3:D4:E5:F6",
        "a1:b2:c3:d4:e5:f6",
    ]
    for mac in valid:
        assert mac_address(mac) == b"\xa1\xb2\xc3\xd4\xe5\xf6"


async def test_invalid_mac_address(hass: HomeAssistant) -> None:
    """Test we do not accept an invalid MAC address."""
    invalid = [
        None,
        123,
        ["a", "b", "c"],
        {"abc": "def"},
        "a1b2c3d4e5f",
        "a1b2.c3d4.e5f",
        "a1-b2-c3-d4-e5-f",
        "a1b2c3d4e5f66",
        "a1b2.c3d4.e5f66",
        "a1-b2-c3-d4-e5-f66",
        "a1b2c3d4e5fg",
        "a1b2.c3d4.e5fg",
        "a1-b2-c3-d4-e5-fg",
        "a1b.2c3d4.e5fg",
        "a1b-2-c3-d4-e5-fg",
    ]
    for mac in invalid:
        with pytest.raises((ValueError, probatio.Invalid)):
            mac_address(mac)


async def test_import_device_filters_magic_entries(hass: HomeAssistant) -> None:
    """Test classic host discovery ignores hostless Magic entries."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENTRY_KIND: ENTRY_KIND_MAGIC_FAMILY,
            "family_id": "family-1",
        },
    ).add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10"},
    ).add_to_hass(hass)

    with patch.object(hass.config_entries.flow, "async_init") as async_init:
        import_device(hass, "192.0.2.10")
        import_device(hass, "192.0.2.11")
        await hass.async_block_till_done()

    async_init.assert_awaited_once()
    assert async_init.await_args.kwargs["data"] == {CONF_HOST: "192.0.2.11"}
