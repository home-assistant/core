"""Test the Litter-Robot vacuum entity."""
import pytest

from homeassistant import config_entries
from homeassistant.components import litterrobot
from homeassistant.components.vacuum import (
    ATTR_PARAMS,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SEND_COMMAND,
    SERVICE_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_DOCKED,
)
from homeassistant.const import ATTR_COMMAND, ATTR_ENTITY_ID

ENTITY_ID = "vacuum.test_litter_box"


async def setup_hub(hass, mock_hub):
    """Load the Litter-Robot vacuum platform with the provided hub."""
    hass.config.components.add(litterrobot.DOMAIN)
    config_entry = config_entries.ConfigEntry(
        1,
        litterrobot.DOMAIN,
        "Mock Title",
        {"host": "mock-host"},
        "test",
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
    )
    mock_hub.config_entry = config_entry
    hass.data[litterrobot.DOMAIN] = {config_entry.entry_id: mock_hub}
    await hass.config_entries.async_forward_entry_setup(config_entry, PLATFORM_DOMAIN)
    await hass.async_block_till_done()


async def test_vacuum(hass, mock_hub):
    """Tests the vacuum entity was set up."""
    await setup_hub(hass, mock_hub)

    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum is not None
    assert vacuum.state == STATE_DOCKED
    assert vacuum.attributes["is_sleeping"] is False


@pytest.mark.parametrize(
    "service,command,extra",
    [
        (SERVICE_START, "start_cleaning", None),
        (SERVICE_TURN_OFF, "set_power_status", None),
        (SERVICE_TURN_ON, "set_power_status", None),
        (
            SERVICE_SEND_COMMAND,
            "reset_waste_drawer",
            {ATTR_COMMAND: "reset_waste_drawer"},
        ),
        (
            SERVICE_SEND_COMMAND,
            "set_sleep_mode",
            {
                ATTR_COMMAND: "set_sleep_mode",
                ATTR_PARAMS: {"enabled": True, "sleep_time": "22:30"},
            },
        ),
    ],
)
async def test_commands(hass, mock_hub, service, command, extra):
    """Test sending commands to the vacuum."""
    await setup_hub(hass, mock_hub)

    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum is not None
    assert vacuum.state == STATE_DOCKED

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    if extra:
        data.update(extra)

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        service,
        data,
        blocking=True,
    )
    getattr(mock_hub.account.robots[0], command).assert_called_once()
