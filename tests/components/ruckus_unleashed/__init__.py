"""Tests for the Ruckus Unleashed integration."""
from unittest.mock import AsyncMock, patch

from aioruckus import AjaxSession, RuckusAjaxApi

from homeassistant.components.ruckus_unleashed.const import (
    API_AP_DEVNAME,
    API_AP_MAC,
    API_AP_MODEL,
    API_AP_SERIALNUMBER,
    API_CLIENT_AP_MAC,
    API_CLIENT_HOSTNAME,
    API_CLIENT_IP,
    API_CLIENT_MAC,
    API_MESH_NAME,
    API_MESH_PSK,
    API_SYS_IDENTITY,
    API_SYS_IDENTITY_NAME,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_SERIAL,
    API_SYS_SYSINFO_VERSION,
    API_SYS_UNLEASHEDNETWORK,
    API_SYS_UNLEASHEDNETWORK_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

DEFAULT_SYSTEM_INFO = {
    API_SYS_IDENTITY: {API_SYS_IDENTITY_NAME: "RuckusUnleashed"},
    API_SYS_SYSINFO: {
        API_SYS_SYSINFO_SERIAL: "123456789012",
        API_SYS_SYSINFO_VERSION: "200.7.10.202 build 141",
    },
    API_SYS_UNLEASHEDNETWORK: {
        API_SYS_UNLEASHEDNETWORK_TOKEN: "un1234567890121680060227001"
    },
}

DEFAULT_MESH_INFO = {
    API_MESH_NAME: "Ruckus Mesh",
    API_MESH_PSK: "",
}

DEFAULT_AP_INFO = [
    {
        API_AP_MAC: "00:11:22:33:44:55",
        API_AP_DEVNAME: "Test Device",
        API_AP_MODEL: "r510",
        API_AP_SERIALNUMBER: DEFAULT_SYSTEM_INFO[API_SYS_SYSINFO][
            API_SYS_SYSINFO_SERIAL
        ],
    }
]

CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

TEST_CLIENT_ENTITY_ID = "device_tracker.ruckus_test_device"
TEST_CLIENT = {
    API_CLIENT_IP: "1.1.1.2",
    API_CLIENT_MAC: "AA:BB:CC:DD:EE:FF",
    API_CLIENT_HOSTNAME: "Ruckus Test Device",
    API_CLIENT_AP_MAC: DEFAULT_AP_INFO[0][API_AP_MAC],
}

DEFAULT_TITLE = DEFAULT_MESH_INFO[API_MESH_NAME]
DEFAULT_UNIQUEID = DEFAULT_SYSTEM_INFO[API_SYS_SYSINFO][API_SYS_SYSINFO_SERIAL]


def mock_config_entry() -> MockConfigEntry:
    """Return a Ruckus Unleashed mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_TITLE,
        unique_id=DEFAULT_UNIQUEID,
        data=CONFIG,
        options=None,
    )


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Ruckus Unleashed integration in Home Assistant."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    # Make device tied to other integration so device tracker entities get enabled
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        name="Device from other integration",
        config_entry_id=other_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, TEST_CLIENT[API_CLIENT_MAC])},
    )

    with RuckusAjaxApiPatchContext():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


class RuckusAjaxApiPatchContext:
    """Context Manager which mocks the Ruckus AjaxSession and RuckusAjaxApi."""

    def __init__(
        self,
        login_mock: AsyncMock = None,
        system_info: dict | None = None,
        mesh_info: dict | None = None,
        active_clients: list[dict] | AsyncMock | None = None,
    ) -> None:
        """Initialize Ruckus Mock Context Manager."""
        self.login_mock = login_mock
        self.system_info = system_info
        self.mesh_info = mesh_info
        self.active_clients = active_clients
        self.patchers = []

    def __enter__(self):
        """Patch RuckusAjaxApi and AjaxSession methods."""
        self.patchers.append(
            patch.object(RuckusAjaxApi, "_get_conf", new=AsyncMock(return_value={}))
        )
        self.patchers.append(
            patch.object(
                RuckusAjaxApi, "get_aps", new=AsyncMock(return_value=DEFAULT_AP_INFO)
            )
        )
        self.patchers.append(
            patch.object(
                RuckusAjaxApi,
                "get_system_info",
                new=AsyncMock(
                    return_value=DEFAULT_SYSTEM_INFO
                    if self.system_info is None
                    else self.system_info
                ),
            )
        )
        self.patchers.append(
            patch.object(
                RuckusAjaxApi,
                "get_mesh_info",
                new=AsyncMock(
                    return_value=DEFAULT_MESH_INFO
                    if self.mesh_info is None
                    else self.mesh_info
                ),
            )
        )
        self.patchers.append(
            patch.object(
                RuckusAjaxApi,
                "get_active_clients",
                new=self.active_clients
                if isinstance(self.active_clients, AsyncMock)
                else AsyncMock(
                    return_value=[TEST_CLIENT]
                    if self.active_clients is None
                    else self.active_clients
                ),
            )
        )
        self.patchers.append(
            patch.object(
                AjaxSession,
                "login",
                new=self.login_mock or AsyncMock(return_value=self),
            )
        )
        self.patchers.append(
            patch.object(AjaxSession, "close", new=AsyncMock(return_value=None))
        )

        def _patched_async_create(
            host: str, username: str, password: str
        ) -> "AjaxSession":
            return AjaxSession(None, host, username, password)

        self.patchers.append(
            patch.object(AjaxSession, "async_create", new=_patched_async_create)
        )

        for patcher in self.patchers:
            patcher.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove RuckusAjaxApi and AjaxSession patches."""
        for patcher in self.patchers:
            patcher.stop()
