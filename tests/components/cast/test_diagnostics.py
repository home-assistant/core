"""Tests for the Google Cast diagnostics."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pychromecast
from pychromecast.const import CAST_TYPE_CHROMECAST, CAST_TYPE_GROUP
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cast.const import DOMAIN
from homeassistant.core import HomeAssistant

SERVICE = pychromecast.discovery.MDNSServiceInfo("the-service")
CHROMECAST_UUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e2")
GROUP_UUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e3")
UNKNOWN_UUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e4")
DYNAMIC_GROUP_UUID = UUID("57355bce-9364-4aa6-ac1e-eb849dccf9e5")


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    get_cast_type_mock: MagicMock,
    get_multizone_status_mock: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    browser = MagicMock(devices={}, zc={})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "ignore_cec": ["Living room TV"],
            "known_hosts": ["192.168.1.10", "192.168.1.11"],
            "uuid": [],
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.cast.discovery.pychromecast.discovery.CastBrowser",
            return_value=browser,
        ) as cast_browser,
        patch(
            "homeassistant.components.cast.discovery.ChromeCastZeroconf.get_zeroconf",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        discovery_callback = cast_browser.call_args[0][0].add_cast

        browser.devices[CHROMECAST_UUID] = pychromecast.models.CastInfo(
            {SERVICE},
            CHROMECAST_UUID,
            "Chromecast Ultra",
            "Living room",
            "192.168.1.10",
            8009,
            CAST_TYPE_CHROMECAST,
            "Google Inc.",
        )
        browser.devices[GROUP_UUID] = pychromecast.models.CastInfo(
            {SERVICE},
            GROUP_UUID,
            "Google Cast Group",
            "Downstairs",
            "192.168.1.11",
            42241,
            CAST_TYPE_GROUP,
            "Google Inc.",
        )
        browser.devices[UNKNOWN_UUID] = pychromecast.models.CastInfo(
            {SERVICE},
            UNKNOWN_UUID,
            "Model 101",
            "Kitchen",
            "192.168.1.12",
            8009,
            None,
            None,
        )
        get_cast_type_mock.return_value = pychromecast.models.CastInfo(
            {SERVICE},
            UNKNOWN_UUID,
            "Model 101",
            "Kitchen",
            "192.168.1.12",
            8009,
            "audio",
            "Cyberdyne Systems",
        )
        get_multizone_status_mock.return_value.dynamic_groups = [
            MagicMock(uuid=DYNAMIC_GROUP_UUID)
        ]
        browser.devices[DYNAMIC_GROUP_UUID] = pychromecast.models.CastInfo(
            {SERVICE},
            DYNAMIC_GROUP_UUID,
            "Google Cast Group",
            "Everywhere",
            "192.168.1.13",
            42242,
            CAST_TYPE_GROUP,
            "Google Inc.",
        )
        # The static group is not reported as discovered
        discovery_callback(CHROMECAST_UUID, "")
        discovery_callback(UNKNOWN_UUID, "")
        discovery_callback(DYNAMIC_GROUP_UUID, "")
        await hass.async_block_till_done(wait_background_tasks=True)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
