"""Test configuration for the ZHA component."""
from unittest import mock
from unittest.mock import patch

import pytest
import zigpy
from zigpy.application import ControllerApplication

from homeassistant import config_entries
from homeassistant.components.zha.core.const import COMPONENTS, DATA_ZHA, DOMAIN
from homeassistant.components.zha.core.gateway import ZHAGateway
from homeassistant.components.zha.core.store import async_get_registry
from homeassistant.helpers.device_registry import async_get_registry as get_dev_reg

from .common import async_setup_entry

FIXTURE_GRP_ID = 0x1001
FIXTURE_GRP_NAME = "fixture group"


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass):
    """Fixture representing a config entry."""
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Mock Title",
        {},
        "test",
        config_entries.CONN_CLASS_LOCAL_PUSH,
        system_options={},
    )
    return config_entry


@pytest.fixture(name="zha_gateway")
async def zha_gateway_fixture(hass, config_entry):
    """Fixture representing a zha gateway.

    Create a ZHAGateway object that can be used to interact with as if we
    had a real zigbee network running.
    """
    for component in COMPONENTS:
        hass.data[DATA_ZHA][component] = hass.data[DATA_ZHA].get(component, {})
    zha_storage = await async_get_registry(hass)
    dev_reg = await get_dev_reg(hass)
    gateway = ZHAGateway(hass, {}, config_entry)
    gateway.zha_storage = zha_storage
    gateway.ha_device_registry = dev_reg
    gateway.application_controller = mock.MagicMock(spec_set=ControllerApplication)
    groups = zigpy.group.Groups(gateway.application_controller)
    groups.listener_event = mock.MagicMock()
    groups.add_group(FIXTURE_GRP_ID, FIXTURE_GRP_NAME, suppress_event=True)
    gateway.application_controller.groups = groups
    return gateway


@pytest.fixture(autouse=True)
async def setup_zha(hass, config_entry):
    """Load the ZHA component.

    This will init the ZHA component. It loads the component in HA so that
    we can test the domains that ZHA supports without actually having a zigbee
    network running.
    """
    # this prevents needing an actual radio and zigbee network available
    with patch("homeassistant.components.zha.async_setup_entry", async_setup_entry):
        hass.data[DATA_ZHA] = {}

        # init ZHA
        await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
        await hass.async_block_till_done()
