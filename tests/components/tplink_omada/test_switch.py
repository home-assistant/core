"""Tests for TP-Link Omada switch entities."""
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion
from tplink_omada_client.definitions import PoEMode
from tplink_omada_client.devices import OmadaSwitch, OmadaSwitchPortDetails
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
    snapshot: SnapshotAssertion,
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
            snapshot,
        )


async def _test_poe_switch(
    hass: HomeAssistant,
    mock_omada_site_client: MagicMock,
    entity_id: str,
    network_switch_mac: str,
    port_num: int,
    snapshot: SnapshotAssertion,
) -> None:
    entity_registry = er.async_get(hass)

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

    mock_omada_site_client.update_switch_port.reset_mock()
    mock_omada_site_client.update_switch_port.return_value = await _update_port_details(
        mock_omada_site_client, port_num, False
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


def call_service(hass: HomeAssistant, service: str, entity_id: str):
    """Call any service on entity."""
    return hass.services.async_call(
        switch.DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
