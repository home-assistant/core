"""Tests for the Huawei LTE switches."""
from unittest.mock import MagicMock, patch

from huawei_lte_api.enums.cradle import ConnectionStatusEnum
from pytest import fixture

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_URL, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry

SWITCH_WIFI_GUEST_NETWORK = "switch.huawei_lte_wifi_guest_network"


@fixture
@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch(
    "homeassistant.components.huawei_lte.Client",
    return_value=MagicMock(
        device=MagicMock(
            information=MagicMock(return_value={"SerialNumber": "test-serial-number"})
        ),
        monitoring=MagicMock(
            check_notifications=MagicMock(return_value={"SmsStorageFull": 0}),
            status=MagicMock(
                return_value={"ConnectionStatus": ConnectionStatusEnum.CONNECTED.value}
            ),
        ),
        wlan=MagicMock(
            multi_basic_settings=MagicMock(
                return_value={
                    "Ssids": {"Ssid": [{"wifiisguestnetwork": "1", "WifiEnable": "0"}]}
                }
            ),
            wifi_feature_switch=MagicMock(return_value={"wifi24g_switch_enable": 1}),
        ),
    ),
)
async def setup_component_with_wifi_guest_network(
    client: MagicMock, hass: HomeAssistant
) -> None:
    """Initialize huawei_lte components."""
    assert client
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    assert await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()


@fixture
@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch(
    "homeassistant.components.huawei_lte.Client",
    return_value=MagicMock(
        device=MagicMock(
            information=MagicMock(return_value={"SerialNumber": "test-serial-number"})
        ),
        monitoring=MagicMock(
            check_notifications=MagicMock(return_value={"SmsStorageFull": 0}),
            status=MagicMock(
                return_value={"ConnectionStatus": ConnectionStatusEnum.CONNECTED.value}
            ),
        ),
        wlan=MagicMock(
            multi_basic_settings=MagicMock(return_value={}),
            wifi_feature_switch=MagicMock(return_value={"wifi24g_switch_enable": 1}),
        ),
    ),
)
async def setup_component_without_wifi_guest_network(
    client: MagicMock, hass: HomeAssistant
) -> None:
    """Initialize huawei_lte components."""
    assert client
    huawei_lte = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://huawei-lte"})
    huawei_lte.add_to_hass(hass)
    assert await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()


def test_huawei_lte_wifi_guest_network_config_entry_when_network_is_not_present(
    hass: HomeAssistant,
    setup_component_without_wifi_guest_network,
) -> None:
    """Test switch wifi guest network config entry when network is not present."""
    entity_registry: EntityRegistry = er.async_get(hass)
    assert not entity_registry.async_is_registered(SWITCH_WIFI_GUEST_NETWORK)


def test_huawei_lte_wifi_guest_network_config_entry_when_network_is_present(
    hass: HomeAssistant,
    setup_component_with_wifi_guest_network,
) -> None:
    """Test switch wifi guest network config entry when network is present."""
    entity_registry: EntityRegistry = er.async_get(hass)
    assert entity_registry.async_is_registered(SWITCH_WIFI_GUEST_NETWORK)


async def test_turn_on_switch_wifi_guest_network(
    hass: HomeAssistant, setup_component_with_wifi_guest_network
) -> None:
    """Test switch wifi guest network turn on method."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_WIFI_GUEST_NETWORK},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(SWITCH_WIFI_GUEST_NETWORK, STATE_ON)
    hass.data[DOMAIN].routers[
        "test-serial-number"
    ].client.wlan.wifi_guest_network_switch.assert_called_once_with(True)


async def test_turn_off_switch_wifi_guest_network(
    hass: HomeAssistant, setup_component_with_wifi_guest_network
) -> None:
    """Test switch wifi guest network turn off method."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_WIFI_GUEST_NETWORK},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.is_state(SWITCH_WIFI_GUEST_NETWORK, STATE_OFF)
    hass.data[DOMAIN].routers[
        "test-serial-number"
    ].client.wlan.wifi_guest_network_switch.assert_called_with(False)
