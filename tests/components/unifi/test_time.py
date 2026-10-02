"""UniFi Network time platform tests."""

from typing import Any
from unittest.mock import patch

import aiounifi
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
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

START = "time.unifi_network_block_streaming_schedule_start"
END = "time.unifi_network_block_streaming_schedule_end"

WEEKLY = {
    "mode": "EVERY_WEEK",
    "repeat_on_days": ["mon", "wed"],
    "time_all_day": False,
    "time_range_start": "15:00",
    "time_range_end": "17:00",
}


def _policy(schedule: dict[str, Any] | None) -> dict[str, Any]:
    """Return the test policy with another schedule, or with none."""
    policy = {k: v for k, v in FIREWALL_POLICY.items() if k != "schedule"}
    if schedule is not None:
        policy["schedule"] = schedule
    return policy


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.TIME]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_schedule_times_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The schedule times are created disabled."""
    for entity_id in (START, END):
        assert hass.states.get(entity_id) is None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("firewall_policy_payload", "start", "end"),
    [
        ([FIREWALL_POLICY], "21:00:00", "08:00:00"),
        ([_policy(WEEKLY)], "15:00:00", "17:00:00"),
        ([_policy({"mode": "ALWAYS"})], STATE_UNKNOWN, STATE_UNKNOWN),
        (
            [_policy({**WEEKLY, "time_all_day": True})],
            STATE_UNKNOWN,
            STATE_UNKNOWN,
        ),
        (
            [
                _policy(
                    {
                        "mode": "EVERY_DAY",
                        "time_range_start": "25:00",
                        "time_range_end": "08:00",
                    }
                )
            ],
            STATE_UNKNOWN,
            "08:00:00",
        ),
        ([_policy({"mode": "SUNRISE"})], STATE_UNKNOWN, STATE_UNKNOWN),
        ([_policy(None)], STATE_UNKNOWN, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_schedule_time_values(hass: HomeAssistant, start: str, end: str) -> None:
    """The times show the schedule's window when its mode has one."""
    assert hass.states.get(START).state == start
    assert hass.states.get(END).state == end


@pytest.mark.parametrize(
    ("entity_id", "value", "expected_schedule"),
    [
        (
            START,
            "22:15:00",
            {
                "mode": "EVERY_DAY",
                "time_range_start": "22:15",
                "time_range_end": "08:00",
            },
        ),
        # Seconds are dropped.
        (
            END,
            "07:30:45",
            {
                "mode": "EVERY_DAY",
                "time_range_start": "21:00",
                "time_range_end": "07:30",
            },
        ),
    ],
)
@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_schedule_time(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    entity_id: str,
    value: str,
    expected_schedule: dict[str, Any],
) -> None:
    """Setting a time sends the whole schedule with that time changed."""
    expected = {**FIREWALL_POLICY, "schedule": expected_schedule}
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/firewall-policies/{FIREWALL_POLICY['_id']}",
        json=expected,
        headers={"content-type": CONTENT_TYPE_JSON},
    )
    call_count = aioclient_mock.call_count

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: value},
        blocking=True,
    )

    assert aioclient_mock.mock_calls[call_count][0] == "put"
    assert aioclient_mock.mock_calls[call_count][2] == expected


@pytest.mark.parametrize(
    "firewall_policy_payload",
    [
        [_policy({"mode": "ALWAYS"})],
        [_policy({**WEEKLY, "time_all_day": True})],
        [_policy({"mode": "SUNRISE"})],
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_set_schedule_time_unused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A time can't be set when the schedule has no window."""
    call_count = aioclient_mock.call_count
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: START, ATTR_TIME: "22:00:00"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "schedule_setting_unused_in_mode"
    assert aioclient_mock.call_count == call_count


@pytest.mark.parametrize("firewall_policy_payload", [[FIREWALL_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_schedule_time_request_failed(
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
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: START, ATTR_TIME: "22:00:00"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "action_request_failed"
    assert hass.states.get(START).state == "21:00:00"
