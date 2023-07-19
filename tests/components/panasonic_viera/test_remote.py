"""Test the Panasonic Viera remote entity."""
from unittest.mock import Mock, call

from panasonic_viera import Keys, SOAPError

from homeassistant.components import automation
from homeassistant.components.panasonic_viera.const import ATTR_UDN, DOMAIN
from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.setup import async_setup_component

from .conftest import MOCK_CONFIG_DATA, MOCK_DEVICE_INFO, MOCK_ENCRYPTION_DATA

from tests.common import MockConfigEntry

FAKE_UUID = "mock-unique-id"


async def setup_panasonic_viera(hass):
    """Initialize integration for tests."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()


async def test_onoff(hass: HomeAssistant, calls, mock_remote) -> None:
    """Test the on/off service calls."""

    await setup_panasonic_viera(hass)
    entity_id = "remote.panasonic_viera_tv"
    data = {ATTR_ENTITY_ID: entity_id}

    device_reg = get_dev_reg(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, FAKE_UUID)})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "panasonic_viera.turn_on",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": "{{ trigger.device_id }}",
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
                {
                    "trigger": {
                        "platform": "panasonic_viera.turn_on",
                        "entity_id": entity_id,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": entity_id,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )

    # simulate tv off when async_update
    mock_remote.get_mute = Mock(side_effect=SOAPError)

    await hass.services.async_call(REMOTE_DOMAIN, SERVICE_TURN_OFF, data)
    await hass.services.async_call(REMOTE_DOMAIN, SERVICE_TURN_ON, data)
    await hass.async_block_till_done()

    power = getattr(Keys.power, "value", Keys.power)
    assert mock_remote.send_key.call_args_list == [call(power)]
    assert len(calls) == 2


async def test_send_command(hass: HomeAssistant, mock_remote) -> None:
    """Test the send_command service call."""

    await setup_panasonic_viera(hass)

    data = {ATTR_ENTITY_ID: "remote.panasonic_viera_tv", ATTR_COMMAND: "command"}
    await hass.services.async_call(REMOTE_DOMAIN, SERVICE_SEND_COMMAND, data)
    await hass.async_block_till_done()

    assert mock_remote.send_key.call_args == call("command")
