"""Contains fixtures for Loqed tests."""

from collections.abc import AsyncGenerator
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from loqedAPI import loqed
import pytest

from homeassistant.components.loqed import DOMAIN
from homeassistant.components.loqed.const import CONF_CLOUDHOOK_URL
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Mock config entry."""

    config = load_fixture("loqed/integration_config.json")
    json_config = json.loads(config)
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data={
            "id": "Foo",
            "bridge_ip": json_config["bridge_ip"],
            "bridge_mdns_hostname": json_config["bridge_mdns_hostname"],
            "bridge_key": json_config["bridge_key"],
            "lock_key_local_id": int(json_config["lock_key_local_id"]),
            "lock_key_key": json_config["lock_key_key"],
            CONF_WEBHOOK_ID: "Webhook_id",
            CONF_API_TOKEN: "Token",
            CONF_NAME: "Home",
        },
    )


@pytest.fixture(name="cloud_config_entry")
def cloud_config_entry_fixture() -> MockConfigEntry:
    """Mock config entry."""

    config = load_fixture("loqed/integration_config.json")
    webhooks_fixture = json.loads(load_fixture("loqed/get_all_webhooks.json"))
    json_config = json.loads(config)
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data={
            "id": "Foo",
            "bridge_ip": json_config["bridge_ip"],
            "bridge_mdns_hostname": json_config["bridge_mdns_hostname"],
            "bridge_key": json_config["bridge_key"],
            "lock_key_local_id": int(json_config["lock_key_local_id"]),
            "lock_key_key": json_config["lock_key_key"],
            CONF_WEBHOOK_ID: "Webhook_id",
            CONF_API_TOKEN: "Token",
            CONF_NAME: "Home",
            CONF_CLOUDHOOK_URL: webhooks_fixture[0]["url"],
        },
    )


@pytest.fixture(name="lock")
def lock_fixture() -> loqed.Lock:
    """Set up a mock implementation of a Lock."""
    webhooks_fixture = json.loads(load_fixture("loqed/get_all_webhooks.json"))

    mock_lock = Mock(spec=loqed.Lock, id="Foo", last_key_id=2)
    mock_lock.name = "LOQED smart lock"
    mock_lock.getWebhooks = AsyncMock(return_value=webhooks_fixture)
    mock_lock.bolt_state = "locked"
    mock_lock.battery_percentage = 90
    return mock_lock


@pytest.fixture(name="integration")
async def integration_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, lock: loqed.Lock
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the loqed integration with a config entry."""
    config: dict[str, Any] = {DOMAIN: {CONF_API_TOKEN: ""}}
    config_entry.add_to_hass(hass)

    lock_status = json.loads(load_fixture("loqed/status_ok.json"))

    with (
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", return_value=lock),
        patch(
            "loqedAPI.loqed.LoqedAPI.async_get_lock_details", return_value=lock_status
        ),
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield config_entry
