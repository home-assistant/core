"""Test KNX init."""

from unittest.mock import patch

import pytest
from xknx.io import (
    DEFAULT_MCAST_GRP,
    DEFAULT_MCAST_PORT,
    ConnectionConfig,
    ConnectionType,
    SecureConfig,
)

from homeassistant.components.knx.config_flow import DEFAULT_ROUTING_IA
from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_FILENAME,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_ROUTING_SECURE,
    CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_ID,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    DOMAIN as KNX_DOMAIN,
    KNXConfigEntryData,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("config_entry_data", "connection_config"),
    [
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
            },
            ConnectionConfig(threaded=True),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING,
                CONF_KNX_LOCAL_IP: "192.168.1.1",
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
            },
            ConnectionConfig(
                connection_type=ConnectionType.ROUTING,
                individual_address=DEFAULT_ROUTING_IA,
                multicast_group=DEFAULT_MCAST_GRP,
                multicast_port=DEFAULT_MCAST_PORT,
                local_ip="192.168.1.1",
                threaded=True,
            ),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                CONF_KNX_ROUTE_BACK: False,
                CONF_KNX_LOCAL_IP: "192.168.1.112",
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
            },
            ConnectionConfig(
                connection_type=ConnectionType.TUNNELING,
                route_back=False,
                gateway_ip="192.168.0.2",
                gateway_port=3675,
                local_ip="192.168.1.112",
                auto_reconnect=True,
                threaded=True,
            ),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
                CONF_KNX_KNXKEY_FILENAME: "knx/keyring.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
            ConnectionConfig(
                connection_type=ConnectionType.TUNNELING_TCP,
                gateway_ip="192.168.0.2",
                gateway_port=3675,
                auto_reconnect=True,
                secure_config=SecureConfig(
                    knxkeys_file_path="keyring.knxkeys", knxkeys_password="password"
                ),
                threaded=True,
            ),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
                CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
                CONF_KNX_KNXKEY_PASSWORD: "password",
            },
            ConnectionConfig(
                connection_type=ConnectionType.TUNNELING_TCP_SECURE,
                gateway_ip="192.168.0.2",
                gateway_port=3675,
                secure_config=SecureConfig(
                    knxkeys_file_path="testcase.knxkeys", knxkeys_password="password"
                ),
                auto_reconnect=True,
                threaded=True,
            ),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_TUNNELING_TCP_SECURE,
                CONF_HOST: "192.168.0.2",
                CONF_PORT: 3675,
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
                CONF_KNX_SECURE_USER_ID: 2,
                CONF_KNX_SECURE_USER_PASSWORD: "password",
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_auth",
            },
            ConnectionConfig(
                connection_type=ConnectionType.TUNNELING_TCP_SECURE,
                gateway_ip="192.168.0.2",
                gateway_port=3675,
                secure_config=SecureConfig(
                    device_authentication_password="device_auth",
                    user_password="password",
                    user_id=2,
                ),
                auto_reconnect=True,
                threaded=True,
            ),
        ),
        (
            {
                CONF_KNX_CONNECTION_TYPE: CONF_KNX_ROUTING_SECURE,
                CONF_KNX_LOCAL_IP: "192.168.1.1",
                CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
                CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
                CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
                CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
                CONF_KNX_INDIVIDUAL_ADDRESS: DEFAULT_ROUTING_IA,
                CONF_KNX_ROUTING_BACKBONE_KEY: "bbaacc44bbaacc44bbaacc44bbaacc44",
                CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE: 2000,
            },
            ConnectionConfig(
                connection_type=ConnectionType.ROUTING_SECURE,
                individual_address=DEFAULT_ROUTING_IA,
                multicast_group=DEFAULT_MCAST_GRP,
                multicast_port=DEFAULT_MCAST_PORT,
                secure_config=SecureConfig(
                    backbone_key="bbaacc44bbaacc44bbaacc44bbaacc44",
                    latency_ms=2000,
                ),
                local_ip="192.168.1.1",
                threaded=True,
            ),
        ),
    ],
)
async def test_init_connection_handling(
    hass: HomeAssistant,
    knx: KNXTestKit,
    config_entry_data: KNXConfigEntryData,
    connection_config: ConnectionConfig,
) -> None:
    """Test correctly generating connection config."""

    config_entry = MockConfigEntry(
        title="KNX",
        domain=KNX_DOMAIN,
        data=config_entry_data,
    )
    knx.mock_config_entry = config_entry
    await knx.setup_integration({})

    assert hass.data.get(KNX_DOMAIN) is not None

    original_connection_config = (
        hass.data[KNX_DOMAIN].connection_config().__dict__.copy()
    )
    del original_connection_config["secure_config"]

    connection_config_dict = connection_config.__dict__.copy()
    del connection_config_dict["secure_config"]

    assert original_connection_config == connection_config_dict

    if connection_config.secure_config is not None:
        assert (
            hass.data[KNX_DOMAIN].connection_config().secure_config.knxkeys_password
            == connection_config.secure_config.knxkeys_password
        )
        assert (
            hass.data[KNX_DOMAIN].connection_config().secure_config.user_password
            == connection_config.secure_config.user_password
        )
        assert (
            hass.data[KNX_DOMAIN].connection_config().secure_config.user_id
            == connection_config.secure_config.user_id
        )
        assert (
            hass.data[KNX_DOMAIN]
            .connection_config()
            .secure_config.device_authentication_password
            == connection_config.secure_config.device_authentication_password
        )
        if connection_config.secure_config.knxkeys_file_path is not None:
            assert (
                connection_config.secure_config.knxkeys_file_path
                in hass.data[KNX_DOMAIN]
                .connection_config()
                .secure_config.knxkeys_file_path
            )


async def test_async_remove_entry(
    hass: HomeAssistant,
    knx: KNXTestKit,
) -> None:
    """Test async_setup_entry (for coverage)."""
    config_entry = MockConfigEntry(
        title="KNX",
        domain=KNX_DOMAIN,
        data={
            CONF_KNX_KNXKEY_FILENAME: "knx/testcase.knxkeys",
        },
    )
    knx.mock_config_entry = config_entry
    await knx.setup_integration({})

    with (
        patch("pathlib.Path.unlink") as unlink_mock,
        patch("pathlib.Path.rmdir") as rmdir_mock,
    ):
        assert await hass.config_entries.async_remove(config_entry.entry_id)
        assert unlink_mock.call_count == 3
        rmdir_mock.assert_called_once()
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries() == []
    assert config_entry.state is ConfigEntryState.NOT_LOADED
