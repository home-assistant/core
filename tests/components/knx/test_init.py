"""Test KNX init."""
import pytest
from xknx import XKNX
from xknx.io import ConnectionConfig, ConnectionType

from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_ROUTING,
    CONF_KNX_TUNNELING,
    DOMAIN as KNX_DOMAIN,
)
from homeassistant.components.knx.schema import ConnectionSchema
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "config_entry_data,connection_config",
    [
        (
            {
                CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            },
            ConnectionConfig(),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
                ConnectionSchema.CONF_KNX_LOCAL_IP: "192.168.1.1",
            },
            ConnectionConfig(
                connection_type=ConnectionType.ROUTING, local_ip="192.168.1.1"
            ),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                ConnectionSchema.CONF_KNX_ROUTE_BACK: False,
                ConnectionSchema.CONF_KNX_LOCAL_IP: "192.168.1.112",
            },
            ConnectionConfig(
                connection_type=ConnectionType.TUNNELING,
                route_back=False,
                gateway_ip="192.168.0.2",
                gateway_port=3675,
                local_ip="192.168.1.112",
                auto_reconnect=True,
            ),
        ),
    ],
)
async def test_init_connection_handling(
    hass: HomeAssistant, knx: KNXTestKit, config_entry_data, connection_config
):
    """Test correctly generating connection config."""

    config_entry = MockConfigEntry(
        title="KNX",
        domain=KNX_DOMAIN,
        data=config_entry_data,
    )
    knx.mock_config_entry = config_entry
    await knx.setup_integration({})

    assert hass.data.get(KNX_DOMAIN) is not None

    assert (
        hass.data[KNX_DOMAIN].connection_config().__dict__ == connection_config.__dict__
    )
