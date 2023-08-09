"""Tests for TP-Link Omada switch entities."""
from unittest.mock import MagicMock

from tplink_omada_client.omadasiteclient import SwitchPortOverrides

from homeassistant.components import switch
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_poe_switches(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test PoE switch."""
    poe_switch_mac = "54-AF-97-00-00-01"
    for i in range(1, 9):
        await _test_poe_switch(
            hass,
            mock_omada_site_client,
            f"switch.test_poe_switch_port_{i}_poe",
            poe_switch_mac,
            i,
        )


async def _test_poe_switch(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    entity_id: str,
    network_switch_mac: str,
    port: int,
) -> None:
    entity_registry = er.async_get(hass)

    poe_enable: bool = True

    async def assert_update_switch_port(
        device, port, overrides: SwitchPortOverrides = None
    ):
        assert device
        assert device.mac == network_switch_mac
        assert port
        assert port.port == port
        assert overrides
        assert overrides.enable_poe == poe_enable

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == "on"
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"{network_switch_mac}_00000000000000000000000{port}_poe"

    mock_omada_site_client.update_switch_port.reset_mock()
    await call_service(hass, "turn_on", entity_id)
    mock_omada_site_client.update_switch_port.assert_called_once()
    device, switch_port = mock_omada_site_client.update_switch_port.call_args.args
    assert_update_switch_port(
        device,
        switch_port,
        **mock_omada_site_client.update_switch_port.call_args.kwargs,
    )

    mock_omada_site_client.update_switch_port.reset_mock()
    poe_enable = False
    await call_service(hass, "turn_off", "switch.test_poe_switch_port_1_poe")
    mock_omada_site_client.update_switch_port.assert_called_once()
    device, switch_port = mock_omada_site_client.update_switch_port.call_args.args
    assert_update_switch_port(
        device,
        switch_port,
        **mock_omada_site_client.update_switch_port.call_args.kwargs,
    )


def call_service(hass, service, entity_id):
    """Call any service on entity."""
    return hass.services.async_call(
        switch.DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
