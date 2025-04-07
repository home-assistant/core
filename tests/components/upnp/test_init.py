"""Test UPnP/IGD setup process."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import copy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from async_upnp_client.exceptions import UpnpCommunicationError
from async_upnp_client.profiles.igd import IgdDevice
import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_FORCE_POLL,
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo

from .conftest import (
    TEST_DISCOVERY,
    TEST_LOCATION,
    TEST_MAC_ADDRESS,
    TEST_ST,
    TEST_UDN,
    TEST_USN,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("ssdp_instant_discovery", "mock_mac_address_from_host")
async def test_async_setup_entry_default(
    hass: HomeAssistant, mock_igd_device: IgdDevice
) -> None:
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        options={
            CONFIG_ENTRY_FORCE_POLL: False,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True

    mock_igd_device.async_subscribe_services.assert_called()


@pytest.mark.usefixtures("ssdp_instant_discovery", "mock_no_mac_address_from_host")
async def test_async_setup_entry_default_no_mac_address(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: None,
        },
        options={
            CONFIG_ENTRY_FORCE_POLL: False,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True


@pytest.mark.usefixtures(
    "ssdp_instant_discovery_multi_location",
    "mock_mac_address_from_host",
)
async def test_async_setup_entry_multi_location(
    hass: HomeAssistant, mock_async_create_device: AsyncMock
) -> None:
    """Test async_setup_entry for a device both seen via IPv4 and IPv6.

    The resulting IPv4 location is preferred/stored.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        options={
            CONFIG_ENTRY_FORCE_POLL: False,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True

    # Ensure that the IPv4 location is used.
    mock_async_create_device.assert_called_once_with(TEST_LOCATION)


@pytest.mark.usefixtures("mock_mac_address_from_host")
async def test_async_setup_udn_mismatch(
    hass: HomeAssistant, mock_async_create_device: AsyncMock
) -> None:
    """Test async_setup_entry for a device which reports a different UDN from SSDP-discovery and device description."""
    test_discovery = copy.deepcopy(TEST_DISCOVERY)
    test_discovery.upnp[ATTR_UPNP_UDN] = "uuid:another_udn"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        options={
            CONFIG_ENTRY_FORCE_POLL: False,
        },
    )

    # Set up device discovery callback.
    async def register_callback(
        hass: HomeAssistant,
        callback: Callable[
            [SsdpServiceInfo, ssdp.SsdpChange], Coroutine[Any, Any, None] | None
        ],
        match_dict: dict[str, str] | None = None,
    ) -> MagicMock:
        """Immediately do callback."""
        await callback(test_discovery, ssdp.SsdpChange.ALIVE)
        return MagicMock()

    with (
        patch(
            "homeassistant.components.ssdp.async_register_callback",
            side_effect=register_callback,
        ),
        patch(
            "homeassistant.components.ssdp.async_get_discovery_info_by_st",
            return_value=[test_discovery],
        ),
    ):
        # Load config_entry.
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is True

    # Ensure that the IPv4 location is used.
    mock_async_create_device.assert_called_once_with(TEST_LOCATION)


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_async_setup_entry_force_poll(
    hass: HomeAssistant, mock_igd_device: IgdDevice
) -> None:
    """Test async_setup_entry with forced polling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        options={
            CONFIG_ENTRY_FORCE_POLL: True,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True

    mock_igd_device.async_subscribe_services.assert_not_called()

    # Ensure that the device is forced to poll.
    mock_igd_device.async_get_traffic_and_status_data.assert_called_with(
        None, force_poll=True
    )


@pytest.mark.usefixtures(
    "ssdp_instant_discovery",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_async_setup_entry_force_poll_subscribe_error(
    hass: HomeAssistant, mock_igd_device: IgdDevice
) -> None:
    """Test async_setup_entry where subscribing fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
        options={
            CONFIG_ENTRY_FORCE_POLL: False,
        },
    )

    # Subscribing partially succeeds, but not completely.
    # Unsubscribing will fail for the subscribed services afterwards.
    mock_igd_device.async_subscribe_services.side_effect = UpnpCommunicationError
    mock_igd_device.async_unsubscribe_services.side_effect = UpnpCommunicationError

    # Load config_entry, should still be able to load, falling back to polling/the old functionality.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True

    # Ensure that the device is forced to poll.
    mock_igd_device.async_get_traffic_and_status_data.assert_called_with(
        None, force_poll=True
    )
