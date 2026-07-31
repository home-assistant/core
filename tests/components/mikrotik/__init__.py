"""Tests for the Mikrotik integration."""

from typing import Any
from unittest.mock import patch

from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import (
    ARP_DATA,
    DHCP_DATA,
    HEALTH_DATA,
    MOCK_DATA,
    SYSTEM_DATA,
    TEST_FIRMWARE,
    TEST_MODEL,
    TEST_SERIAL_NUMBER,
    WIFIWAVE2_DATA,
    WIRELESS_DATA,
)

from tests.common import MockConfigEntry


def _build_command_responses(
    *,
    support_wireless: bool,
    support_wifiwave2: bool,
    dhcp_data: list[dict[str, Any]],
    wireless_data: list[dict[str, Any]],
    wifiwave2_data: list[dict[str, Any]],
    health_data: list[dict[str, Any]],
    system_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build mocked service responses for the Mikrotik coordinator."""
    return {
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY]: [
            {"name": "Mikrotik"}
        ],
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.INFO]: [
            {
                "model": TEST_MODEL,
                "current-firmware": TEST_FIRMWARE,
                "serial-number": TEST_SERIAL_NUMBER,
            }
        ],
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_CAPSMAN]: [],
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]: support_wireless,
        mikrotik.const.MIKROTIK_SERVICES[
            mikrotik.const.IS_WIFIWAVE2
        ]: support_wifiwave2,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIFI]: False,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]: dhcp_data,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]: wireless_data,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIFIWAVE2]: wifiwave2_data,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.ARP]: ARP_DATA,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.HEALTH]: health_data,
        mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.SYSTEM]: system_data,
    }


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    *,
    command_responses: dict[str, Any],
) -> None:
    """Set up the component with mocked Mikrotik command responses."""
    config_entry.add_to_hass(hass)

    def mock_command(
        self,
        cmd: str,
        params: dict[str, Any] | None = None,
        suppress_errors: bool = False,
    ) -> Any:
        return command_responses.get(cmd, {})

    with (
        patch("librouteros.connect"),
        patch.object(mikrotik.coordinator.MikrotikData, "command", new=mock_command),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


def create_mock_config_entry(
    *,
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    domain: str = DOMAIN,
) -> MockConfigEntry:
    """Create a Mikrotik test config entry with optional overrides."""
    return MockConfigEntry(
        domain=domain,
        data=data or MOCK_DATA,
        options=options or {},
        version=1,
        minor_version=1,
    )


async def setup_mikrotik_entry(
    hass: HomeAssistant,
    **kwargs: Any,
) -> MockConfigEntry:
    """Set up a Mikrotik config entry with defaults that tests can override."""
    options = dict(kwargs.get("options", {}))
    if "force_dhcp" in kwargs:
        options["force_dhcp"] = True
    if "arp_ping" in kwargs:
        options["arp_ping"] = True

    config_entry = create_mock_config_entry(options=options)

    command_responses = _build_command_responses(
        support_wireless=kwargs.get("support_wireless", True),
        support_wifiwave2=kwargs.get("support_wifiwave2", False),
        dhcp_data=kwargs.get("dhcp_data", DHCP_DATA),
        wireless_data=kwargs.get("wireless_data", WIRELESS_DATA),
        wifiwave2_data=kwargs.get("wifiwave2_data", WIFIWAVE2_DATA),
        health_data=kwargs.get("health_data", HEALTH_DATA),
        system_data=kwargs.get("system_data", SYSTEM_DATA),
    )

    await setup_integration(hass, config_entry, command_responses=command_responses)
    return config_entry
