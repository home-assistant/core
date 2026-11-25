"""Tests for the Huawei LTE DHCP switch."""

from unittest.mock import MagicMock, patch

from huawei_lte_api.api.Dhcp import DhcpSettings
from huawei_lte_api.exceptions import (
    ResponseErrorException,
    ResponseErrorNotSupportedException,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests import ConnectTimeout

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.huawei_lte.switch import HuaweiLteDhcpSwitch
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import magic_client

SWITCH_DHCP = "switch.test_router_dhcp_server"


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


async def test_entity_created(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Add the switch when the router returns DHCP settings."""
    await setup_entry(hass, magic_client())

    assert entity_registry.async_is_registered(SWITCH_DHCP)


@pytest.mark.parametrize(
    "error",
    [
        ResponseErrorNotSupportedException("not supported", 100002),
        TypeError("invalid settings"),
    ],
    ids=["unsupported", "unparsable"],
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
    ("method", "initial", "requested"),
    [("turn_on", False, True), ("turn_off", True, False)],
    ids=["enable", "disable"],
)
def test_change_state(method: str, initial: bool, requested: bool) -> None:
    """Send the requested state and update the entity."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = [
        DhcpSettings(dhcp_status=initial),
        DhcpSettings(dhcp_status=requested),
    ]

    getattr(switch, method)()

    sent = router.client.dhcp.set_settings.call_args.args[0]
    assert sent.dhcp_status is requested
    assert switch.is_on is requested
    switch.schedule_update_ha_state.assert_called_once()


def test_unchanged_state_does_not_write() -> None:
    """Do not write when the router already has the requested state."""
    switch, router = make_switch()
    router.client.dhcp.settings.return_value = DhcpSettings(dhcp_status=True)

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
def test_command_error(error: Exception) -> None:
    """Report failures to read or write as a Home Assistant error."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = error

    with pytest.raises(HomeAssistantError) as err:
        switch.turn_on()

    assert err.value.translation_key == "dhcp_command_failed"
    switch.schedule_update_ha_state.assert_not_called()


def test_unconfirmed_state() -> None:
    """Do not report success when the router keeps the previous state."""
    switch, router = make_switch()
    router.client.dhcp.settings.side_effect = [
        DhcpSettings(dhcp_status=False),
        DhcpSettings(dhcp_status=False),
    ]

    with pytest.raises(HomeAssistantError) as err:
        switch.turn_on()

    assert err.value.translation_key == "dhcp_state_not_confirmed"
    assert not switch.is_on
    switch.schedule_update_ha_state.assert_not_called()
