"""UniFi Network number platform tests."""

from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONTENT_TYPE_JSON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    DEFAULT_HOST,
    DEFAULT_SITE,
    WAN_NETWORKS,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
)

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

FAILOVER_PRIORITY_ENTITY_ID = "number.internet_1_failover_priority"
LOAD_BALANCE_WEIGHT_ENTITY_ID = "number.internet_1_load_balance_weight"


@pytest.mark.parametrize("network_payload", [[WAN_NETWORKS[0]]])
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.NUMBER]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.parametrize(
    "site_payload",
    [[{"desc": "Site name", "name": "site_id", "role": "not admin", "_id": "1"}]],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_no_entities_without_admin(hass: HomeAssistant) -> None:
    """Verify no entities are created without admin rights."""
    assert len(hass.states.async_entity_ids(NUMBER_DOMAIN)) == 0


@pytest.mark.parametrize(
    ("network_payload", "expected_entities"),
    [
        ([{**WAN_NETWORKS[0], "wan_failover_priority": None}], 1),
        ([{**WAN_NETWORKS[0], "wan_load_balance_weight": None}], 1),
        ([{**WAN_NETWORKS[0], "purpose": "corporate"}], 0),
    ],
    ids=["no_failover_priority", "no_load_balance_weight", "not_a_wan"],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_unsupported_network(hass: HomeAssistant, expected_entities: int) -> None:
    """Verify entities are only created for the reported fields."""
    assert len(hass.states.async_entity_ids(NUMBER_DOMAIN)) == expected_entities


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.parametrize(
    ("entity_id", "field", "value"),
    [
        (FAILOVER_PRIORITY_ENTITY_ID, "wan_failover_priority", 4),
        (LOAD_BALANCE_WEIGHT_ENTITY_ID, "wan_load_balance_weight", 60),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    entity_id: str,
    field: str,
    value: int,
) -> None:
    """Verify setting a value writes the full network back."""
    assert hass.states.get(entity_id).state == str(WAN_NETWORKS[0][field])

    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/rest/networkconf/{WAN_NETWORKS[0]['_id']}",
        json={"meta": {"rc": "ok"}, "data": []},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    expected_call = deepcopy(WAN_NETWORKS[0])
    expected_call[field] = value
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == expected_call


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.usefixtures("config_entry_setup")
async def test_websocket_update(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Verify state is updated from a networkconf websocket message."""
    assert hass.states.get(FAILOVER_PRIORITY_ENTITY_ID).state == "1"

    network = deepcopy(WAN_NETWORKS[0])
    network["wan_failover_priority"] = 3
    mock_websocket_message(message=MessageKey.NETWORK_CONF_UPDATED, data=network)
    await hass.async_block_till_done()

    assert hass.states.get(FAILOVER_PRIORITY_ENTITY_ID).state == "3"


NETWORK_URL = (
    f"https://{DEFAULT_HOST}:1234/api/s/{DEFAULT_SITE}"
    f"/rest/networkconf/{WAN_NETWORKS[0]['_id']}"
)


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.parametrize(
    ("response", "expected_reason"),
    [
        pytest.param(
            {
                "json": {"meta": {"rc": "error", "msg": "api.err.Unknown"}, "data": []},
                "headers": {"content-type": CONTENT_TYPE_JSON},
            },
            "api.err.Unknown",
            id="controller_error",
        ),
        pytest.param(
            {"status": HTTPStatus.BAD_GATEWAY},
            f"Call {NETWORK_URL} received 502 bad gateway",
            id="transport_error",
        ),
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_set_value_request_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    response: dict[str, Any],
    expected_reason: str,
) -> None:
    """Verify a failing request raises a translated error with the reason."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(NETWORK_URL, **response)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: FAILOVER_PRIORITY_ENTITY_ID, ATTR_VALUE: 2},
            blocking=True,
        )
    assert exc_info.value.translation_key == "action_request_rejected"
    assert exc_info.value.translation_placeholders == {"reason": expected_reason}
