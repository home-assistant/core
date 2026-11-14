"""Tests for LG webOS TV Wake-on-LAN support."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import automation
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.components.webostv.const import (
    CONF_MAC_ADDRESSES,
    CONF_SOURCES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_CLIENT_SECRET,
    CONF_HOST,
    CONF_MAC,
    SERVICE_TURN_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from . import setup_webostv
from .const import ENTITY_ID, HOST
from .test_media_player import mock_scan_interval

MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("connection_info", "expected_macs", "expected_interfaces", "expected_display"),
    [
        pytest.param(
            {"wiredInfo": {"macAddress": "AA-BB-CC-DD-EE-FF"}},
            [MAC_ADDRESS],
            {"wiredInfo": MAC_ADDRESS},
            {"wired_mac": MAC_ADDRESS, "wifi_mac": "—"},
            id="wired",
        ),
        pytest.param(
            {"wifiInfo": {"macAddress": MAC_ADDRESS}},
            [MAC_ADDRESS],
            {"wifiInfo": MAC_ADDRESS},
            {"wired_mac": "—", "wifi_mac": MAC_ADDRESS},
            id="wifi",
        ),
        pytest.param(
            {
                "wiredInfo": {"macAddress": MAC_ADDRESS},
                "wifiInfo": {"macAddress": "11:22:33:44:55:66"},
            },
            [MAC_ADDRESS, "11:22:33:44:55:66"],
            {"wiredInfo": MAC_ADDRESS, "wifiInfo": "11:22:33:44:55:66"},
            {"wired_mac": MAC_ADDRESS, "wifi_mac": "11:22:33:44:55:66"},
            id="both-interfaces",
        ),
        pytest.param(
            {
                "wiredInfo": {"macAddress": "AA-BB-CC-DD-EE-FF"},
                "wifiInfo": {"macAddress": MAC_ADDRESS},
            },
            [MAC_ADDRESS],
            {"wiredInfo": MAC_ADDRESS, "wifiInfo": MAC_ADDRESS},
            {"wired_mac": MAC_ADDRESS, "wifi_mac": MAC_ADDRESS},
            id="duplicate",
        ),
        pytest.param(
            {
                "wiredInfo": {"macAddress": "invalid"},
                "wifiInfo": {"macAddress": MAC_ADDRESS},
            },
            [MAC_ADDRESS],
            {"wifiInfo": MAC_ADDRESS},
            {"wired_mac": "—", "wifi_mac": MAC_ADDRESS},
            id="invalid-wired-address",
        ),
    ],
)
async def test_discover_mac_address(
    hass: HomeAssistant,
    client: Mock,
    mock_send_magic_packet: Mock,
    freezer: FrozenDateTimeFactory,
    connection_info: dict[str, dict[str, str]],
    expected_macs: list[str],
    expected_interfaces: dict[str, str],
    expected_display: dict[str, str],
) -> None:
    """Discover a MAC on connection and retain it across key changes and reloads."""
    client.is_connected.return_value = False
    client.tv_info.connection = connection_info
    entry = await setup_webostv(hass)

    assert entry.data[CONF_MAC_ADDRESSES] == expected_interfaces
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES] & (
        MediaPlayerEntityFeature.TURN_ON
    )

    client.client_key = "updated_key"
    client.tv_info.connection = {}
    await mock_scan_interval(hass, freezer)
    assert entry.data[CONF_CLIENT_SECRET] == "updated_key"
    assert entry.data[CONF_MAC_ADDRESSES] == expected_interfaces

    client.tv_state.is_on = False
    client.connect.side_effect = TimeoutError
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await mock_scan_interval(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_send_magic_packet.assert_called_once_with(*expected_macs)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "automatic"
    assert result["description_placeholders"] == expected_display


@pytest.mark.parametrize(
    "connection_info",
    [
        pytest.param({}, id="unavailable"),
        pytest.param({"wiredInfo": {}}, id="missing-address"),
        pytest.param({"wiredInfo": {"macAddress": "invalid"}}, id="invalid-address"),
        pytest.param({"wiredInfo": None}, id="invalid-interface"),
        pytest.param({"wifiInfo": {"macAddress": 123}}, id="non-string-address"),
    ],
)
async def test_mac_discovery_retry(
    hass: HomeAssistant,
    client: Mock,
    freezer: FrozenDateTimeFactory,
    connection_info: dict[str, object],
) -> None:
    """A failed MAC lookup allows setup and is retried on reconnect."""
    client.is_connected.return_value = False
    client.tv_info.connection = connection_info
    entry = await setup_webostv(hass)

    assert CONF_MAC_ADDRESSES not in entry.data
    assert not hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES] & (
        MediaPlayerEntityFeature.TURN_ON
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    assert result["description_placeholders"] == {}

    client.tv_info.connection = {"wiredInfo": {"macAddress": MAC_ADDRESS}}
    await mock_scan_interval(hass, freezer)

    assert entry.data[CONF_MAC_ADDRESSES] == {"wiredInfo": MAC_ADDRESS}
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES] & (
        MediaPlayerEntityFeature.TURN_ON
    )


async def test_manual_mac_overrides_discovery(
    hass: HomeAssistant,
    client: Mock,
    mock_send_magic_packet: Mock,
) -> None:
    """Allow overriding the MAC addresses reported by the TV."""
    client.is_connected.return_value = False
    client.tv_info.connection = {"wiredInfo": {"macAddress": MAC_ADDRESS}}
    entry = await setup_webostv(hass)
    manual_mac = "11:22:33:44:55:66"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["Live TV"], CONF_MAC: manual_mac},
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_send_magic_packet.assert_called_once_with(manual_mac)
    assert entry.data[CONF_MAC_ADDRESSES] == {"wiredInfo": MAC_ADDRESS}

    mock_send_magic_packet.reset_mock()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "manual"
    assert result["description_placeholders"] == {"mac_address": manual_mac}
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SOURCES: ["Live TV"], CONF_MAC: ""}
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_send_magic_packet.assert_called_once_with(MAC_ADDRESS)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "automatic"
    assert result["description_placeholders"] == {
        "wired_mac": MAC_ADDRESS,
        "wifi_mac": "—",
    }


@pytest.mark.parametrize(
    "saved_data",
    [
        pytest.param({CONF_MAC: MAC_ADDRESS}, id="single-address"),
        pytest.param({CONF_MAC_ADDRESSES: [MAC_ADDRESS]}, id="address-list"),
    ],
)
async def test_previously_discovered_mac(
    hass: HomeAssistant,
    client: Mock,
    mock_send_magic_packet: Mock,
    saved_data: dict[str, str | list[str]],
) -> None:
    """Keep using a MAC saved by the previous discovery implementation."""
    entry = await setup_webostv(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, **saved_data})
    client.is_connected.return_value = False
    client.connect.side_effect = TimeoutError
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_send_magic_packet.assert_called_once_with(MAC_ADDRESS)

    client.connect.side_effect = None
    client.tv_info.connection = {"wiredInfo": {"macAddress": "11:22:33:44:55:66"}}
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.data[CONF_MAC_ADDRESSES] == {"wiredInfo": "11:22:33:44:55:66"}
    mock_send_magic_packet.reset_mock()
    await hass.services.async_call(
        "media_player", SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_send_magic_packet.assert_called_once_with("11:22:33:44:55:66")


@pytest.mark.parametrize(
    ("source", "initial_data", "user_input"),
    [
        pytest.param(SOURCE_REAUTH, {CONF_HOST: HOST}, {}, id="reauth"),
        pytest.param(
            SOURCE_RECONFIGURE, None, {CONF_HOST: "new_host"}, id="reconfigure"
        ),
    ],
)
async def test_discovered_mac_preserved(
    hass: HomeAssistant,
    client: Mock,
    source: str,
    initial_data: dict[str, str] | None,
    user_input: dict[str, str],
) -> None:
    """Retain the discovered address when reauthenticating or changing hosts."""
    client.is_connected.return_value = False
    client.tv_info.connection = {"wiredInfo": {"macAddress": MAC_ADDRESS}}
    entry = await setup_webostv(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=initial_data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_MAC_ADDRESSES] == {"wiredInfo": MAC_ADDRESS}


async def test_discovered_mac_redacted(
    hass: HomeAssistant,
    client: Mock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Redact an automatically discovered MAC from diagnostics."""
    client.is_connected.return_value = False
    client.tv_info.connection = {"wiredInfo": {"macAddress": MAC_ADDRESS}}
    entry = await setup_webostv(hass)
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["entry"]["data"][CONF_MAC_ADDRESSES] == "**REDACTED**"
    assert diagnostics["client"]["tv_info"]["connection"]["wiredInfo"] == {
        "macAddress": "**REDACTED**"
    }


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
