"""Test emoncms sensor."""

from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.emoncms.const import CONF_ONLY_INCLUDE_FEEDID, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_PLATFORM, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import EMONCMS_FAILURE, FEEDS, get_feed

from tests.common import async_fire_time_changed

YAML = {
    CONF_PLATFORM: "emoncms",
    CONF_API_KEY: "my_api_key",
    CONF_ID: 1,
    CONF_URL: "http://1.1.1.1",
    CONF_ONLY_INCLUDE_FEEDID: [1, 2],
    "scan_interval": 30,
}


@pytest.fixture
def emoncms_yaml_config() -> ConfigType:
    """Mock emoncms configuration from yaml."""
    return {"sensor": YAML}


def get_entity_ids(feeds: list[dict[str, Any]]) -> list[str]:
    """Get emoncms entity ids."""
    return [
        f"{SENSOR_DOMAIN}.{DOMAIN}_{feed["name"].replace(' ', '_')}" for feed in feeds
    ]


def get_feeds(nbs: list[int]) -> list[dict[str, Any]]:
    """Get feeds."""
    return [feed for feed in FEEDS if feed["id"] in str(nbs)]


async def test_coordinator_update(
    hass: HomeAssistant,
    emoncms_yaml_config: ConfigType,
    snapshot: SnapshotAssertion,
    emoncms_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update."""
    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [get_feed(1, unit="°C")],
    }
    await async_setup_component(hass, SENSOR_DOMAIN, emoncms_yaml_config)
    await hass.async_block_till_done()
    feeds = get_feeds([1])
    for entity_id in get_entity_ids(feeds):
        state = hass.states.get(entity_id)
        assert state == snapshot(name=entity_id)

    async def skip_time() -> None:
        freezer.tick(60)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [get_feed(1, unit="°C", value=24.04, timestamp=1665509670)],
    }

    await skip_time()

    for entity_id in get_entity_ids(feeds):
        state = hass.states.get(entity_id)
        assert state.attributes["LastUpdated"] == 1665509670
        assert state.state == "24.04"

    emoncms_client.async_request.return_value = EMONCMS_FAILURE

    await skip_time()

    assert f"Error fetching {DOMAIN}_coordinator data" in caplog.text
