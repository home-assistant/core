"""Tests for the Lupusec integration setup."""

from unittest.mock import MagicMock, patch

import lupupy.constants as CONST

from homeassistant.components.lupusec.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

MOCK_DATA = {
    CONF_HOST: "test-host.lan",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


def _mock_lupusec_system() -> MagicMock:
    """Return a mocked Lupusec system with an alarm and one binary sensor."""
    system = MagicMock()
    system.model = 2

    alarm = MagicMock()
    alarm.name = "Alarm Panel"
    alarm.device_id = "0"
    alarm.is_standby = True
    alarm.is_away = False
    alarm.is_home = False
    alarm.is_alarm_triggered = False
    system.get_alarm.return_value = alarm

    sensor = MagicMock()
    sensor.device_id = "sensor_1"
    sensor.name = "Front Door"
    sensor.type = "Türkontakt"
    sensor.generic_type = "door"
    sensor.is_on = False

    system.get_devices.side_effect = lambda generic_type: (
        [] if generic_type == CONST.TYPE_SWITCH else [sensor]
    )
    return system


async def test_child_device_links_to_parent(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the child device is linked to the alarm panel via via_device_id.

    Only the binary_sensor platform is forwarded, so the alarm panel (parent)
    device is not created by the sibling alarm_control_panel platform. The child
    can therefore only resolve its via_device_id if the parent was registered at
    setup, before the platforms were forwarded.
    """
    entry = MockConfigEntry(domain=DOMAIN, title=MOCK_DATA[CONF_HOST], data=MOCK_DATA)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.lupusec.lupupy.Lupusec",
            return_value=_mock_lupusec_system(),
        ),
        patch(
            "homeassistant.components.lupusec.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert parent is not None
    assert parent.name == "Alarm Panel"
    assert parent.model == "Lupusec-XT2"

    child = device_registry.async_get_device_by_identifier(
        (DOMAIN, "sensor_1"), entry.entry_id
    )
    assert child is not None
    assert child.via_device_id == parent.id
