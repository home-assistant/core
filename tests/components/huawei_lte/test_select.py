"""Tests for the Huawei LTE selects."""
from unittest.mock import MagicMock, patch

from huawei_lte_api.enums.net import LTEBandEnum, NetworkBandEnum, NetworkModeEnum

from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.select import SERVICE_SELECT_OPTION
from homeassistant.components.select.const import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, CONF_URL
from homeassistant.core import HomeAssistant

from . import magic_client

from tests.common import MockConfigEntry

SELECT_NETWORK_MODE = "select.lte_preferred_network_mode"


@patch("homeassistant.components.huawei_lte.Connection", MagicMock())
@patch("homeassistant.components.huawei_lte.Client")
async def test_set_net_mode(client, hass: HomeAssistant) -> None:
    """Test setting network mode."""
    client.return_value = magic_client({})
    huawei_lte = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: "http://huawei-lte.example.com"}
    )
    huawei_lte.add_to_hass(hass)
    await hass.config_entries.async_setup(huawei_lte.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: SELECT_NETWORK_MODE,
            ATTR_OPTION: NetworkModeEnum.MODE_4G_3G_AUTO.value,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    client.return_value.net.set_net_mode.assert_called_once()
    client.return_value.net.set_net_mode.assert_called_with(
        LTEBandEnum.ALL, NetworkBandEnum.ALL, NetworkModeEnum.MODE_4G_3G_AUTO.value
    )
