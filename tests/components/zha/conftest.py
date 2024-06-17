"""Test configuration for the ZHA component."""

import pytest
import zigpy.config

import homeassistant.components.zha.const as zha_const

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
async def config_entry_fixture() -> MockConfigEntry:
    """Fixture representing a config entry."""
    return MockConfigEntry(
        version=3,
        domain=zha_const.DOMAIN,
        data={
            zigpy.config.CONF_DEVICE: {zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB0"},
            zha_const.CONF_RADIO_TYPE: "ezsp",
        },
        options={
            zha_const.CUSTOM_CONFIGURATION: {
                zha_const.ZHA_OPTIONS: {
                    zha_const.CONF_ENABLE_ENHANCED_LIGHT_TRANSITION: True,
                    zha_const.CONF_GROUP_MEMBERS_ASSUME_STATE: False,
                },
                zha_const.ZHA_ALARM_OPTIONS: {
                    zha_const.CONF_ALARM_ARM_REQUIRES_CODE: False,
                    zha_const.CONF_ALARM_MASTER_CODE: "4321",
                    zha_const.CONF_ALARM_FAILED_TRIES: 2,
                },
            }
        },
    )
