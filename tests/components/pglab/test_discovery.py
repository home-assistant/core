"""The tests for the PG LAB Electronics  discovery device."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_common import get_device_discovery_payload, send_discovery_message

from tests.typing import MqttMockHAClient


async def test_device_discover(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_reg,
    entity_reg,
    setup_pglab,
) -> None:
    """Test setting up a device."""

    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=2,
    )

    await send_discovery_message(hass, payload)

    # Verify device and registry entries are created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None
    assert device_entry.configuration_url == f"http://{payload['ip']}/"
    assert device_entry.manufacturer == "PG LAB Electronics"
    assert device_entry.model == payload["type"]
    assert device_entry.name == payload["name"]
    assert device_entry.sw_version == payload["fw"]


async def test_device_update(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_reg,
    entity_reg,
    setup_pglab,
    snapshot: SnapshotAssertion,
) -> None:
    """Test update a device."""
    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=2,
    )

    await send_discovery_message(hass, payload)

    # Verify device is created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None

    # update device
    payload["fw"] = "1.0.1"
    payload["hw"] = "1.0.8"

    await send_discovery_message(hass, payload)

    # Verify device is created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "1.0.1"
    assert device_entry.hw_version == "1.0.8"


async def test_device_remove(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device_reg,
    entity_reg,
    setup_pglab,
) -> None:
    """Test remove a device."""
    payload = get_device_discovery_payload(
        number_of_shutters=0,
        number_of_boards=2,
    )

    await send_discovery_message(hass, payload)

    # Verify device is created
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is not None

    await send_discovery_message(hass, None)

    # Verify device entry is removed
    device_entry = device_reg.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, payload["mac"])}
    )
    assert device_entry is None
