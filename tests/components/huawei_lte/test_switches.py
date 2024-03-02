"""Tests for the Huawei LTE switches."""
from unittest.mock import MagicMock, patch

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_URL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import magic_client

from tests.common import MockConfigEntry

SWITCH_WIFI_GUEST_NETWORK = "switch.lte_wi_fi_guest_network"


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch("homeassistant.components.huawei_lte.Client", return_value=magic_client({}))
async def test_huawei_lte_wifi_guest_network_config_entry_when_network_is_not_present(
    client,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch wifi guest network config entry when network is not present."""
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(SWITCH_WIFI_GUEST_NETWORK)


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch(
    "homeassistant.components.huawei_lte.Client",
    return_value=magic_client(
        {"Ssids": {"Ssid": [{"wifiisguestnetwork": "1", "WifiEnable": "0"}]}}
    ),
)
async def test_huawei_lte_wifi_guest_network_config_entry_when_network_is_present(
    client,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch wifi guest network config entry when network is present."""
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    assert entity_registry.async_is_registered(SWITCH_WIFI_GUEST_NETWORK)


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch("homeassistant.components.huawei_lte.Client")
async def test_turn_on_switch_wifi_guest_network(client, hass: HomeAssistant) -> None:
    """Test switch wifi guest network turn on method."""
    client.return_value = magic_client(
        {"Ssids": {"Ssid": [{"wifiisguestnetwork": "1", "WifiEnable": "0"}]}}
    )
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_WIFI_GUEST_NETWORK},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(SWITCH_WIFI_GUEST_NETWORK, STATE_ON)
    client.return_value.wlan.wifi_guest_network_switch.assert_called_once_with(True)


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch("homeassistant.components.huawei_lte.Client")
async def test_turn_off_switch_wifi_guest_network(client, hass: HomeAssistant) -> None:
    """Test switch wifi guest network turn off method."""
    client.return_value = magic_client(
        {"Ssids": {"Ssid": [{"wifiisguestnetwork": "1", "WifiEnable": "1"}]}}
    )
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_WIFI_GUEST_NETWORK},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(SWITCH_WIFI_GUEST_NETWORK, STATE_OFF)
    client.return_value.wlan.wifi_guest_network_switch.assert_called_with(False)


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch(
    "homeassistant.components.huawei_lte.Client",
    return_value=magic_client({"Ssids": {"Ssid": "str"}}),
)
async def test_huawei_lte_wifi_guest_network_config_entry_when_ssid_is_str(
    client,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch wifi guest network config entry when ssid is a str.

    Issue #76244. Huawai models: H312-371, E5372 and E8372.
    """
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(SWITCH_WIFI_GUEST_NETWORK)


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch(
    "homeassistant.components.huawei_lte.Client",
    return_value=magic_client({"Ssids": {"Ssid": None}}),
)
async def test_huawei_lte_wifi_guest_network_config_entry_when_ssid_is_none(
    client,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch wifi guest network config entry when ssid is a None.

    Issue #76244.
    """
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    assert not entity_registry.async_is_registered(SWITCH_WIFI_GUEST_NETWORK)
