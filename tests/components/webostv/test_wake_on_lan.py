"""Tests for LG webOS TV Wake-on-LAN support."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import automation
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.webostv.const import CONF_SOURCES
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_CLIENT_SECRET,
    CONF_MAC,
    SERVICE_TURN_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID
from .test_media_player import mock_scan_interval

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"


async def test_wake_disconnected_tv(
    hass: HomeAssistant,
    client: Mock,
    mock_send_magic_packet: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Wake a disconnected TV and retain its MAC across reconnects and reloads."""
    client.is_connected.return_value = False
    entry = await setup_webostv(hass, options={CONF_MAC: MAC_ADDRESS})

    assert entry.options[CONF_MAC] == MAC_ADDRESS
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES] & (
        MediaPlayerEntityFeature.TURN_ON
    )

    client.tv_state.is_on = False
    client.connect.side_effect = TimeoutError
    await mock_scan_interval(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_send_magic_packet.assert_called_once_with(MAC_ADDRESS)

    client.connect.side_effect = None
    client.client_key = "updated_key"
    await mock_scan_interval(hass, freezer)

    assert entry.options[CONF_MAC] == MAC_ADDRESS
    assert entry.data[CONF_CLIENT_SECRET] == "updated_key"

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    mock_send_magic_packet.reset_mock()

    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_send_magic_packet.assert_called_once_with(MAC_ADDRESS)


async def test_turn_on_automation_overrides_wake_on_lan(
    hass: HomeAssistant,
    client: Mock,
    mock_send_magic_packet: Mock,
    service_calls: list[ServiceCall],
) -> None:
    """Prefer a configured turn-on automation over sending a magic packet."""
    client.is_connected.return_value = False
    await setup_webostv(hass, options={CONF_MAC: MAC_ADDRESS})
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "triggers": [
                        {"trigger": "webostv.turn_on", "entity_id": ENTITY_ID}
                    ],
                    "actions": [{"action": "test.automation"}],
                }
            ]
        },
    )

    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert len(service_calls) == 2
    assert service_calls[1].service == "automation"
    mock_send_magic_packet.assert_not_called()


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize(
    ("mac", "expected_options"),
    [
        pytest.param(
            "AA-BB-CC-DD-EE-FF",
            {CONF_SOURCES: ["Live TV"], CONF_MAC: MAC_ADDRESS},
            id="configure",
        ),
        pytest.param("", {CONF_SOURCES: ["Live TV"]}, id="remove"),
    ],
)
async def test_wake_on_lan_options(
    hass: HomeAssistant, mac: str, expected_options: dict[str, str | list[str]]
) -> None:
    """Configure or remove Wake-on-LAN while preserving selected sources."""
    entry = await setup_webostv(hass, options={CONF_MAC: MAC_ADDRESS})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SOURCES: ["Live TV"], CONF_MAC: mac}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == expected_options


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize("mac", ["invalid", "aa:bb:cc:dd:ee:gg"])
async def test_invalid_mac(hass: HomeAssistant, mac: str) -> None:
    """Reject invalid MAC addresses before saving options."""
    entry = await setup_webostv(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SOURCES: ["Live TV"], CONF_MAC: mac}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAC: "invalid_mac"}
    assert CONF_MAC not in entry.options


@pytest.mark.usefixtures("client")
async def test_mac_redacted(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Redact the configured MAC address from diagnostics."""
    entry = await setup_webostv(hass, options={CONF_MAC: MAC_ADDRESS})
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diagnostics["entry"]["options"][CONF_MAC] == "**REDACTED**"
