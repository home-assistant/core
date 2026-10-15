"""Test the Xiaomi Aqara base entity."""

from collections import defaultdict
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.xiaomi_aqara import const
from homeassistant.components.xiaomi_aqara.entity import TIME_TILL_UNAVAILABLE
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_HOST = "1.2.3.4"
TEST_PORT = 1234
TEST_PROTOCOL = "1.1.1"
TEST_MAC = "ab:cd:ef:00:11:22"
TEST_DOOR_SID = "158d0001a2b3c5"


async def _setup_gateway_with_door_sensor(hass: HomeAssistant) -> tuple[Mock, str]:
    """Set up the integration with a single door sensor, return gateway and entity_id."""
    mock_gateway = Mock()
    mock_gateway.sid = TEST_MAC.replace(":", "").lower()
    mock_gateway.callbacks = defaultdict(list)
    mock_gateway.devices = {
        "binary_sensor": [
            {
                "sid": TEST_DOOR_SID,
                "model": "magnet",
                "proto": TEST_PROTOCOL,
                "data": {},
                "raw_data": {"cmd": "report"},
            }
        ],
        "sensor": [],
    }

    mock_multicast = Mock()
    mock_multicast.start_listen = AsyncMock()
    mock_multicast.stop_listen = Mock()

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=TEST_MAC,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_MAC: TEST_MAC,
            const.CONF_INTERFACE: "any",
            CONF_PROTOCOL: TEST_PROTOCOL,
            const.CONF_KEY: None,
            const.CONF_SID: mock_gateway.sid,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.xiaomi_aqara.XiaomiGateway",
            return_value=mock_gateway,
        ),
        patch(
            "homeassistant.components.xiaomi_aqara.AsyncXiaomiGatewayMulticast",
            return_value=mock_multicast,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        BINARY_SENSOR_DOMAIN, const.DOMAIN, f"status{TEST_DOOR_SID}"
    )
    assert entity_id is not None
    return mock_gateway, entity_id


async def test_entity_removal_removes_push_callback(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test removing an entity removes its push callback from the gateway."""
    mock_gateway, entity_id = await _setup_gateway_with_door_sensor(hass)
    entity = hass.data[BINARY_SENSOR_DOMAIN].get_entity(entity_id)
    # The battery sensor of the same device shares the sid.
    callbacks = mock_gateway.callbacks[TEST_DOOR_SID]
    assert len(callbacks) == 2
    assert entity.push_data in callbacks

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert len(callbacks) == 1
    assert entity.push_data not in callbacks


async def test_entity_removal_cancels_unavailability_tracker(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test removing an entity cancels its unavailability tracker."""
    _, entity_id = await _setup_gateway_with_door_sensor(hass)
    entity = hass.data[BINARY_SENSOR_DOMAIN].get_entity(entity_id)
    assert entity.available

    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass, utcnow() + TIME_TILL_UNAVAILABLE + timedelta(seconds=1)
    )
    await hass.async_block_till_done()

    # A still-scheduled tracker would have marked the removed entity unavailable.
    assert entity.available
    assert hass.states.get(entity_id) is None
