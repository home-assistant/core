"""Tests for the Huawei LTE DHCP switch."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from huawei_lte_api.api.Dhcp import DhcpSettings
from huawei_lte_api.exceptions import (
    ResponseErrorException,
    ResponseErrorNotSupportedException,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from requests import ConnectTimeout

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.huawei_lte.switch import HuaweiLteDhcpSwitch
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import (
    CONF_URL,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import magic_client

SWITCH_DHCP = "switch.test_router_dhcp_server"
SCAN_INTERVAL = timedelta(seconds=30)

SETTINGS = DhcpSettings(
    dhcp_ip_address="192.168.1.254",
    dhcp_lan_netmask="255.255.255.0",
    dhcp_status=False,
    dhcp_start_ip_address="192.168.1.20",
    dhcp_end_ip_address="192.168.1.80",
    dhcp_lease_time=3600,
    dns_status=True,
    primary_dns="192.168.1.10",
    secondary_dns="192.168.1.11",
)


def make_client(settings: DhcpSettings) -> tuple[MagicMock, dict[str, DhcpSettings]]:
    """Create a client whose DHCP endpoint behaves like a router."""
    router = {"settings": settings}
    client = magic_client()
    client.dhcp.settings.side_effect = lambda: replace(router["settings"])
    client.dhcp.set_settings.side_effect = lambda sent: router.update(
        settings=replace(sent)
    )
    return client, router


def make_switch() -> tuple[HuaweiLteDhcpSwitch, MagicMock]:
    """Create a switch with a mocked router."""
    router = MagicMock()
    switch = HuaweiLteDhcpSwitch(router)
    switch.schedule_update_ha_state = MagicMock()
    return switch, router


async def setup_entry(hass: HomeAssistant, client: MagicMock) -> None:
    """Set up the integration with the given client."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def call_switch(hass: HomeAssistant, service: SwitchService) -> None:
    """Call a switch service on the DHCP switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {TargetKey.ENTITY_ID: SWITCH_DHCP},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_entity_created(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Add the switch with the state reported by the router."""
    client, _ = make_client(SETTINGS)

    await setup_entry(hass, client)

    assert entity_registry.async_is_registered(SWITCH_DHCP)
    assert hass.states.is_state(SWITCH_DHCP, STATE_OFF)


@pytest.mark.parametrize(
    "error",
    [
        ResponseErrorNotSupportedException("not supported", 100002),
        TypeError("invalid settings"),
        ConnectTimeout(),
    ],
    ids=["unsupported", "unparsable", "request-error"],
)
async def test_entity_not_created(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, error: Exception
) -> None:
    """Skip the switch when the router cannot provide the DHCP settings."""
    client = magic_client()
    client.dhcp.settings.side_effect = error

    await setup_entry(hass, client)

    assert not entity_registry.async_is_registered(SWITCH_DHCP)


@pytest.mark.parametrize(
    ("initial", "service", "requested", "expected"),
    [
        (False, SwitchService.TURN_ON, True, STATE_ON),
        (True, SwitchService.TURN_OFF, False, STATE_OFF),
    ],
    ids=["enable", "disable"],
)
async def test_switch_service(
    hass: HomeAssistant,
    initial: bool,
    service: SwitchService,
    requested: bool,
    expected: str,
) -> None:
    """Change the DHCP state through the switch services."""
    client, router = make_client(replace(SETTINGS, dhcp_status=initial))
    await setup_entry(hass, client)

    await call_switch(hass, service)

    assert hass.states.is_state(SWITCH_DHCP, expected)
    assert router["settings"].dhcp_status is requested


async def test_services_preserve_other_settings(hass: HomeAssistant) -> None:
    """Send every DHCP setting back unchanged except the server state."""
    client, router = make_client(SETTINGS)
    await setup_entry(hass, client)

    await call_switch(hass, SwitchService.TURN_ON)

    sent = client.dhcp.set_settings.call_args.args[0]
    assert sent == replace(SETTINGS, dhcp_status=True)
    assert router["settings"] == replace(SETTINGS, dhcp_status=True)


async def test_entity_tracks_router_changes(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Follow a DHCP state change made outside Home Assistant."""
    client, router = make_client(SETTINGS)
    await setup_entry(hass, client)
    assert hass.states.is_state(SWITCH_DHCP, STATE_OFF)

    router["settings"] = replace(router["settings"], dhcp_status=True)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.is_state(SWITCH_DHCP, STATE_ON)


async def test_entity_unavailable_and_recovers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Become unavailable when a poll fails and recover after a successful one."""
    client, router = make_client(SETTINGS)
    await setup_entry(hass, client)
    assert hass.states.is_state(SWITCH_DHCP, STATE_OFF)

    client.dhcp.settings.side_effect = ConnectTimeout()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.is_state(SWITCH_DHCP, STATE_UNAVAILABLE)

    router["settings"] = replace(router["settings"], dhcp_status=True)
    client.dhcp.settings.side_effect = lambda: replace(router["settings"])
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.is_state(SWITCH_DHCP, STATE_ON)


def test_unchanged_state_does_not_write() -> None:
    """Do not write when the router already has the requested state."""
    switch, router = make_switch()
    router.client.dhcp.settings.return_value = replace(SETTINGS, dhcp_status=True)

    switch.turn_on()

    router.client.dhcp.set_settings.assert_not_called()
    assert switch.is_on


@pytest.mark.parametrize(
    "error",
    [
        ResponseErrorException("boom", 1),
        ConnectTimeout(),
        TypeError("invalid settings"),
        ValueError("invalid lease time"),
        KeyError("DhcpStatus"),
    ],
    ids=["device-error", "timeout", "invalid-type", "invalid-value", "missing-field"],
)
def test_read_error(error: Exception) -> None:
    """Report a failure to read the settings as a Home Assistant error."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        switch.turn_on()

    assert err.value.translation_key == "dhcp_command_failed"
    switch.schedule_update_ha_state.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [ResponseErrorException("boom", 1), ConnectTimeout()],
    ids=["device-error", "timeout"],
)
def test_write_error(error: Exception) -> None:
    """Report a failure to write the settings as a Home Assistant error."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = [
        replace(SETTINGS),
        replace(SETTINGS),
    ]
    router.client.dhcp.set_settings.side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        switch.turn_on()

    assert err.value.translation_key == "dhcp_command_failed"
    switch.schedule_update_ha_state.assert_not_called()


def test_confirmation_read_error() -> None:
    """Report a failure to read the new state as a Home Assistant error."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = [
        replace(SETTINGS),
        ConnectTimeout(),
    ]

    with pytest.raises(HomeAssistantError) as err:
        switch.turn_on()

    assert err.value.translation_key == "dhcp_command_failed"
    switch.schedule_update_ha_state.assert_not_called()


def test_unconfirmed_state() -> None:
    """Do not report success when the router keeps the previous state."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = [
        replace(SETTINGS),
        replace(SETTINGS),
    ]

    with pytest.raises(HomeAssistantError) as err:
        switch.turn_on()

    assert err.value.translation_key == "dhcp_state_not_confirmed"
    assert not switch.is_on
    switch.schedule_update_ha_state.assert_not_called()
