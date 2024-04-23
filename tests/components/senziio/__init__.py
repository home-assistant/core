"""Tests for the Senziio integration."""

from ipaddress import ip_address

from senziio import Senziio

from homeassistant.components import zeroconf
from homeassistant.components.senziio import DOMAIN
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_MODEL, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_mqtt_message

A_DEVICE_ID = "theia-pro-2F3D56AA1234"
A_DEVICE_MODEL = "Theia Pro"
A_FRIENDLY_NAME = "A Friendly Name"
ANOTHER_DEVICE_ID = "theia-pro-AD2BF63DF999"

ENTRY_DATA = {
    CONF_UNIQUE_ID: A_DEVICE_ID,
    CONF_MODEL: A_DEVICE_MODEL,
    CONF_FRIENDLY_NAME: A_FRIENDLY_NAME,
    "fw-version": "1.2.3",
    "hw-version": "1.0.0",
    "mac-address": "1A:2B:3C:4D:5E:6F",
    "serial-number": "theia-pro-2F3D56AA1234",
}

CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    title=A_FRIENDLY_NAME,
    unique_id=A_DEVICE_ID,
    data=ENTRY_DATA,
)

DEVICE_INFO = {
    "model": "Theia Pro",
    "fw-version": "1.2.3",
    "hw-version": "1.0.0",
    "mac-address": "1A:2B:3C:4D:5E:6F",
    "serial-number": "theia-pro-2F3D56AA1234",
}

ZEROCONF_DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname=f"senziio-{A_DEVICE_ID}.local.",
    name=f"senziio-{A_DEVICE_ID}._http._tcp.local.",
    port=0,
    properties={
        "device_id": A_DEVICE_ID,
        "device_model": A_DEVICE_MODEL,
    },
    type="_http._tcp.local.",
)


class FakeSenziioDevice(Senziio):
    """Fake Senziio device for testing."""

    def __init__(self, device_info: dict | None = None) -> None:
        """Initialize with expected info."""
        super().__init__(
            device_info.get("serial-number", ""), device_info.get("model", ""), None
        )
        self._device_info = device_info or {}

    async def get_info(self) -> dict[str, str]:
        """Get device info."""
        return self._device_info


async def when_message_received_is(hass: HomeAssistant, topic: str, payload: str):
    """Emulate receiving a MQTT message."""
    async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done()


def assert_entity_state_is(hass: HomeAssistant, entity: str, state: str):
    """Check if given entity has the given state."""
    assert hass.states.get(entity).state == state
