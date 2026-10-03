"""UniFi Network select platform tests."""

from copy import deepcopy
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONTENT_TYPE_JSON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import WAN_NETWORKS, ConfigEntryFactoryType, WebsocketMessageMock

from tests.common import MockConfigEntry, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

LOAD_BALANCING_ENTITY_ID = "select.internet_1_load_balancing"


@pytest.mark.parametrize("network_payload", [[WAN_NETWORKS[0]]])
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.SELECT]):
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
    assert len(hass.states.async_entity_ids(SELECT_DOMAIN)) == 0


@pytest.mark.parametrize(
    "network_payload",
    [
        [{**WAN_NETWORKS[0], "wan_load_balance_type": None}],
        [{**WAN_NETWORKS[0], "purpose": "corporate"}],
    ],
    ids=["no_load_balance_type", "not_a_wan"],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_unsupported_network(hass: HomeAssistant) -> None:
    """Verify no entity is created for networks without load balancing."""
    assert len(hass.states.async_entity_ids(SELECT_DOMAIN)) == 0


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.parametrize("option", ["weighted", "failover-only"])
async def test_select_load_balancing(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    option: str,
) -> None:
    """Verify selecting a load balancing option writes the full network back."""
    assert hass.states.get(LOAD_BALANCING_ENTITY_ID).state == "failover-only"

    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/rest/networkconf/{WAN_NETWORKS[0]['_id']}",
        json={"meta": {"rc": "ok"}, "data": []},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: LOAD_BALANCING_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    expected_call = deepcopy(WAN_NETWORKS[0])
    expected_call["wan_load_balance_type"] = option
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == expected_call


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.usefixtures("config_entry_setup")
async def test_websocket_update(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Verify state is updated from a networkconf websocket message."""
    assert hass.states.get(LOAD_BALANCING_ENTITY_ID).state == "failover-only"

    network = deepcopy(WAN_NETWORKS[0])
    network["wan_load_balance_type"] = "weighted"
    mock_websocket_message(message=MessageKey.NETWORK_CONF_UPDATED, data=network)
    await hass.async_block_till_done()

    assert hass.states.get(LOAD_BALANCING_ENTITY_ID).state == "weighted"


@pytest.mark.parametrize("network_payload", [WAN_NETWORKS])
@pytest.mark.parametrize(
    ("error_message", "expected_translation_key", "expected_placeholders"),
    [
        pytest.param(
            "api.err.MissingWeightedWanNetwork",
            "wan_load_balance_weighted_required",
            None,
            id="missing_weighted_wan",
        ),
        pytest.param(
            "api.err.Unknown",
            "action_request_rejected",
            {"reason": "api.err.Unknown"},
            id="unknown_error",
        ),
    ],
)
async def test_select_option_request_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    error_message: str,
    expected_translation_key: str,
    expected_placeholders: dict[str, str] | None,
) -> None:
    """Verify a rejected request raises a translated error."""
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/rest/networkconf/{WAN_NETWORKS[0]['_id']}",
        json={"meta": {"rc": "error", "msg": error_message}, "data": []},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: LOAD_BALANCING_ENTITY_ID, ATTR_OPTION: "weighted"},
            blocking=True,
        )
    assert exc_info.value.translation_key == expected_translation_key
    assert exc_info.value.translation_placeholders == expected_placeholders
