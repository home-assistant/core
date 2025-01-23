"""Tests for TP-Link Omada switch entities."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from syrupy.assertion import SnapshotAssertion
from tplink_omada_client import SwitchPortOverrides
from tplink_omada_client.definitions import PoEMode
from tplink_omada_client.devices import (
    OmadaGateway,
    OmadaGatewayPortConfig,
    OmadaGatewayPortStatus,
    OmadaSwitch,
    OmadaSwitchPortDetails,
)
from tplink_omada_client.exceptions import InvalidDevice

from homeassistant.components import switch
from homeassistant.components.tplink_omada.coordinator import POLL_GATEWAY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

UPDATE_INTERVAL = timedelta(seconds=10)
POLL_INTERVAL = timedelta(seconds=POLL_GATEWAY + 10)


async def test_poe_switches(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test PoE switch."""
    poe_switch_mac = "54-AF-97-00-00-01"
    await _test_poe_switch(
        hass,
        mock_omada_site_client,
        "switch.test_poe_switch_port_1_poe",
        poe_switch_mac,
        1,
        snapshot,
        entity_registry,
    )

    await _test_poe_switch(
        hass,
        mock_omada_site_client,
        "switch.test_poe_switch_port_2_renamed_port_poe",
        poe_switch_mac,
        2,
        snapshot,
        entity_registry,
    )


async def test_sfp_port_has_no_poe_switch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test PoE switch SFP ports have no PoE controls."""
    entity = hass.states.get("switch.test_poe_switch_port_9_poe")
    assert entity is None
    entity = hass.states.get("switch.test_poe_switch_port_8_poe")
    assert entity is not None


async def test_gateway_connect_ipv4_switch(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""
    gateway_mac = "AA-BB-CC-DD-EE-FF"

    entity_id = "switch.test_router_port_4_internet_connected"
    entity = hass.states.get(entity_id)
    assert entity == snapshot

    test_gateway = await mock_omada_site_client.get_gateway(gateway_mac)
    port_status = test_gateway.port_status[3]
    assert port_status.port_number == 4

    mock_omada_site_client.set_gateway_wan_port_connect_state = AsyncMock(
        return_value=(
            _get_updated_gateway_port_status(
                mock_omada_site_client, test_gateway, 3, "internetState", 0
            )
        )
    )
    await call_service(hass, "turn_off", entity_id)
    mock_omada_site_client.set_gateway_wan_port_connect_state.assert_called_once_with(
        4, False, test_gateway, ipv6=False
    )

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "off"

    mock_omada_site_client.set_gateway_wan_port_connect_state.reset_mock()
    mock_omada_site_client.set_gateway_wan_port_connect_state.return_value = (
        _get_updated_gateway_port_status(
            mock_omada_site_client, test_gateway, 3, "internetState", 1
        )
    )
    await call_service(hass, "turn_on", entity_id)
    mock_omada_site_client.set_gateway_wan_port_connect_state.assert_called_once_with(
        4, True, test_gateway, ipv6=False
    )

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "on"


async def test_gateway_port_poe_switch(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""
    gateway_mac = "AA-BB-CC-DD-EE-FF"

    entity_id = "switch.test_router_port_5_poe"
    entity = hass.states.get(entity_id)
    assert entity == snapshot

    test_gateway = await mock_omada_site_client.get_gateway(gateway_mac)
    port_config = test_gateway.port_configs[4]
    assert port_config.port_number == 5

    mock_omada_site_client.set_gateway_port_settings = AsyncMock(
        return_value=(OmadaGatewayPortConfig(port_config.raw_data, poe_enabled=False))
    )
    await call_service(hass, "turn_off", entity_id)
    _assert_gateway_poe_set(mock_omada_site_client, test_gateway, False)

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "off"

    mock_omada_site_client.set_gateway_port_settings.reset_mock()
    mock_omada_site_client.set_gateway_port_settings.return_value = port_config
    await call_service(hass, "turn_on", entity_id)
    _assert_gateway_poe_set(mock_omada_site_client, test_gateway, True)

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "on"


async def test_gateway_wan_port_has_no_poe_switch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test PoE switch SFP ports have no PoE controls."""
    entity = hass.states.get("switch.test_router_port_1_poe")
    assert entity is None
    entity = hass.states.get("switch.test_router_port_9_poe")
    assert entity is not None


def _assert_gateway_poe_set(mock_omada_site_client, test_gateway, poe_enabled: bool):
    (
        called_port,
        called_settings,
        called_gateway,
    ) = mock_omada_site_client.set_gateway_port_settings.call_args.args
    mock_omada_site_client.set_gateway_port_settings.assert_called_once()
    assert called_port == 5
    assert called_settings.enable_poe is poe_enabled
    assert called_gateway == test_gateway


async def test_gateway_api_fail_disables_switch_entities(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switches."""
    entity_id = "switch.test_router_port_4_internet_connected"
    entity = hass.states.get(entity_id)
    assert entity == snapshot
    assert entity.state == "on"

    mock_omada_site_client.get_gateway.reset_mock()
    mock_omada_site_client.get_gateway.side_effect = InvalidDevice("Expected error")

    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "unavailable"


async def test_gateway_port_change_disables_switch_entities(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test gateway connected switch reconfigure."""

    gateway_mac = "AA-BB-CC-DD-EE-FF"
    test_gateway = await mock_omada_site_client.get_gateway(gateway_mac)

    entity_id = "switch.test_router_port_4_internet_connected"
    entity = hass.states.get(entity_id)
    assert entity == snapshot
    assert entity.state == "on"

    mock_omada_site_client.get_gateway.reset_mock()
    # Set Port 4 to LAN mode
    _get_updated_gateway_port_status(mock_omada_site_client, test_gateway, 3, "mode", 1)

    async_fire_time_changed(hass, utcnow() + POLL_INTERVAL)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "unavailable"


async def _test_poe_switch(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    entity_id: str,
    network_switch_mac: str,
    port_num: int,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    def assert_update_switch_port(
        device: OmadaSwitch,
        switch_port_details: OmadaSwitchPortDetails,
        poe_enabled: bool,
        overrides: SwitchPortOverrides = None,
    ) -> None:
        assert device
        assert device.mac == network_switch_mac
        assert switch_port_details
        assert switch_port_details.port == port_num
        assert overrides
        assert overrides.enable_poe == poe_enabled

    entity = hass.states.get(entity_id)
    assert entity == snapshot
    entry = entity_registry.async_get(entity_id)
    assert entry == snapshot

    mock_omada_site_client.update_switch_port = AsyncMock(
        return_value=await _update_port_details(mock_omada_site_client, port_num, False)
    )

    await call_service(hass, "turn_off", entity_id)
    mock_omada_site_client.update_switch_port.assert_called_once()
    (
        device,
        switch_port_details,
    ) = mock_omada_site_client.update_switch_port.call_args.args

    assert_update_switch_port(
        device,
        switch_port_details,
        False,
        **mock_omada_site_client.update_switch_port.call_args.kwargs,
    )
    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()
    entity = hass.states.get(entity_id)
    assert entity.state == "off"

    mock_omada_site_client.update_switch_port.reset_mock()
    mock_omada_site_client.update_switch_port.return_value = await _update_port_details(
        mock_omada_site_client, port_num, True
    )
    await call_service(hass, "turn_on", entity_id)
    mock_omada_site_client.update_switch_port.assert_called_once()
    device, switch_port = mock_omada_site_client.update_switch_port.call_args.args
    assert_update_switch_port(
        device,
        switch_port,
        True,
        **mock_omada_site_client.update_switch_port.call_args.kwargs,
    )
    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()
    entity = hass.states.get(entity_id)
    assert entity.state == "on"


async def _update_port_details(
    mock_omada_site_client: MagicMock,
    port_num: int,
    poe_enabled: bool,
) -> OmadaSwitchPortDetails:
    switch_ports = await mock_omada_site_client.get_switch_ports()
    port_details: OmadaSwitchPortDetails = None
    for details in switch_ports:
        if details.port == port_num:
            port_details = details
            break

    assert port_details is not None
    raw_data = port_details.raw_data.copy()
    raw_data["poe"] = PoEMode.ENABLED if poe_enabled else PoEMode.DISABLED
    return OmadaSwitchPortDetails(raw_data)


def _get_updated_gateway_port_status(
    mock_omada_site_client: MagicMock,
    gateway: OmadaGateway,
    port: int,
    key: str,
    value: Any,
) -> OmadaGatewayPortStatus:
    gateway_data = gateway.raw_data.copy()
    gateway_data["portStats"][port][key] = value
    mock_omada_site_client.get_gateway.reset_mock()
    mock_omada_site_client.get_gateway.return_value = OmadaGateway(gateway_data)
    return OmadaGatewayPortStatus(gateway_data["portStats"][port])


def call_service(hass: HomeAssistant, service: str, entity_id: str) -> ServiceResponse:
    """Call any service on entity."""
    return hass.services.async_call(
        switch.DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
