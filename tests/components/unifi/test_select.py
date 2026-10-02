"""UniFi Network select platform tests."""

from typing import Any
from unittest.mock import patch

import aiounifi
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.unifi.const import CONF_SITE_ID, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONTENT_TYPE_JSON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType
from .test_sensor import FIREWALL_POLICY

ENTITY_ID = "select.unifi_network_block_streaming_schedule"


def _policy(schedule: dict[str, Any] | None) -> dict[str, Any]:
    """Return the test policy with another schedule, or with none."""
    policy = {k: v for k, v in FIREWALL_POLICY.items() if k != "schedule"}
    if schedule is not None:
        policy["schedule"] = schedule
    return policy


def _mock_put(
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    response: dict[str, Any],
) -> None:
    """Mock the controller accepting a firewall policy update."""
    aioclient_mock.put(
        f"https://{config_entry.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry.data[CONF_SITE_ID]}"
        f"/firewall-policies/{FIREWALL_POLICY['_id']}",
        json=response,
        headers={"content-type": CONTENT_TYPE_JSON},
    )


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_schedule_mode_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The schedule select is created disabled."""
    assert hass.states.get(ENTITY_ID) is None
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("firewall_policy_payload", "expected"),
    [
        ([_policy({"mode": "ALWAYS"})], "always"),
        ([FIREWALL_POLICY], "every_day"),
        ([_policy({"mode": "EVERY_WEEK", "repeat_on_days": ["mon"]})], "every_week"),
        ([_policy({"mode": "ONE_TIME_ONLY", "date": "2026-01-15"})], "one_time"),
        ([_policy({"mode": "CUSTOM"})], "custom"),
        ([_policy({"mode": "SUNRISE"})], STATE_UNKNOWN),
        ([_policy(None)], STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_schedule_mode_states(hass: HomeAssistant, expected: str) -> None:
    """The select shows the policy's schedule mode."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("firewall_policy_payload", "option", "expected_schedule"),
    [
        ([FIREWALL_POLICY], "always", {"mode": "ALWAYS"}),
        # 23:30 UTC is already the 16th on the controller (Europe/Stockholm).
        (
            [FIREWALL_POLICY],
            "one_time",
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-16",
                "time_range_start": "21:00",
                "time_range_end": "08:00",
            },
        ),
        (
            [_policy({"mode": "ALWAYS"})],
            "every_day",
            {
                "mode": "EVERY_DAY",
                "time_range_start": "09:00",
                "time_range_end": "12:00",
            },
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_schedule_mode(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    config_entry_factory: ConfigEntryFactoryType,
    firewall_policy_payload: list[dict[str, Any]],
    option: str,
    expected_schedule: dict[str, Any],
) -> None:
    """Selecting a mode sends a clean schedule for it."""
    freezer.move_to("2026-01-15 23:30:00+00:00")
    config_entry = await config_entry_factory()
    expected = {**firewall_policy_payload[0], "schedule": expected_schedule}
    _mock_put(aioclient_mock, config_entry, expected)
    call_count = aioclient_mock.call_count

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )

    assert aioclient_mock.mock_calls[call_count][0] == "put"
    assert aioclient_mock.mock_calls[call_count][2] == expected


@pytest.mark.parametrize("option", ["every_week", "custom"])
@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_select_schedule_mode_not_supported(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, option: str
) -> None:
    """Modes that need day selection can't be chosen yet."""
    call_count = aioclient_mock.call_count
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "schedule_mode_not_supported"
    assert aioclient_mock.call_count == call_count
    assert hass.states.get(ENTITY_ID).state == "every_day"


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_schedule_mode_request_failed(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """A rejected request raises and leaves the state unchanged."""
    with (
        patch.object(
            config_entry_setup.runtime_data.api,
            "request",
            side_effect=aiounifi.AiounifiException,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "always"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "action_request_failed"
    assert hass.states.get(ENTITY_ID).state == "every_day"
