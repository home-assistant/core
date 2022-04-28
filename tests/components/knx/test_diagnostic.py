"""Tests for the diagnostics data provided by the KNX integration."""
from unittest.mock import patch

from aiohttp import ClientSession
from xknx import XKNX
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT

from homeassistant.components.knx.const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    DOMAIN as KNX_DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.knx.conftest import KNXTestKit


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
):
    """Test diagnostics."""
    await knx.setup_integration({})

    with patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        # Overwrite the version for this test since we don't want to change this with every library bump
        knx.xknx.version = "1.0.0"
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        ) == {
            "config_entry_data": {
                "connection_type": "automatic",
                "individual_address": "15.15.250",
                "multicast_group": "224.0.23.12",
                "multicast_port": 3671,
                "rate_limit": 20,
                "state_updater": True,
            },
            "configuration_error": None,
            "configuration_yaml": None,
            "xknx": {"current_address": "0.0.0", "version": "1.0.0"},
        }


async def test_diagnostic_config_error(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_config_entry: MockConfigEntry,
    knx: KNXTestKit,
):
    """Test diagnostics."""
    await knx.setup_integration({})

    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value={"knx": {"wrong_key": {}}},
    ):
        # Overwrite the version for this test since we don't want to change this with every library bump
        knx.xknx.version = "1.0.0"
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        ) == {
            "config_entry_data": {
                "connection_type": "automatic",
                "individual_address": "15.15.250",
                "multicast_group": "224.0.23.12",
                "multicast_port": 3671,
                "rate_limit": 20,
                "state_updater": True,
            },
            "configuration_error": "extra keys not allowed @ data['knx']['wrong_key']",
            "configuration_yaml": {"wrong_key": {}},
            "xknx": {"current_address": "0.0.0", "version": "1.0.0"},
        }


async def test_diagnostic_redact(
    hass: HomeAssistant,
    hass_client: ClientSession,
):
    """Test diagnostics redacting data."""
    mock_config_entry: MockConfigEntry = MockConfigEntry(
        title="KNX",
        domain=KNX_DOMAIN,
        data={
            CONF_KNX_CONNECTION_TYPE: CONF_KNX_AUTOMATIC,
            CONF_KNX_RATE_LIMIT: CONF_KNX_DEFAULT_RATE_LIMIT,
            CONF_KNX_STATE_UPDATER: CONF_KNX_DEFAULT_STATE_UPDATER,
            CONF_KNX_MCAST_PORT: DEFAULT_MCAST_PORT,
            CONF_KNX_MCAST_GRP: DEFAULT_MCAST_GRP,
            CONF_KNX_INDIVIDUAL_ADDRESS: XKNX.DEFAULT_ADDRESS,
            CONF_KNX_KNXKEY_PASSWORD: "password",
            CONF_KNX_SECURE_USER_PASSWORD: "user_password",
            CONF_KNX_SECURE_DEVICE_AUTHENTICATION: "device_authentication",
        },
    )
    knx: KNXTestKit = KNXTestKit(hass, mock_config_entry)
    await knx.setup_integration({})

    with patch("homeassistant.config.async_hass_config_yaml", return_value={}):
        # Overwrite the version for this test since we don't want to change this with every library bump
        knx.xknx.version = "1.0.0"
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, mock_config_entry
        ) == {
            "config_entry_data": {
                "connection_type": "automatic",
                "individual_address": "15.15.250",
                "multicast_group": "224.0.23.12",
                "multicast_port": 3671,
                "rate_limit": 20,
                "state_updater": True,
                "knxkeys_password": "**REDACTED**",
                "user_password": "**REDACTED**",
                "device_authentication": "**REDACTED**",
            },
            "configuration_error": None,
            "configuration_yaml": None,
            "xknx": {"current_address": "0.0.0", "version": "1.0.0"},
        }
