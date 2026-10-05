"""UniFi Network date platform tests."""

from typing import Any
from unittest.mock import patch

import aiounifi
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.date import (
    ATTR_DATE,
    DOMAIN as DATE_DOMAIN,
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

START = "date.unifi_network_block_streaming_schedule_start_date"
END = "date.unifi_network_block_streaming_schedule_end_date"

ONE_TIME = {
    "mode": "ONE_TIME_ONLY",
    "date": "2026-01-15",
    "time_range_start": "21:30",
    "time_range_end": "08:30",
}
CUSTOM = {
    "mode": "CUSTOM",
    "date_start": "2026-01-05",
    "date_end": "2026-01-30",
    "repeat_on_days": ["mon", "fri"],
    "time_all_day": True,
}
ONE_TIME_POLICY = {**FIREWALL_POLICY, "schedule": ONE_TIME}
CUSTOM_POLICY = {**FIREWALL_POLICY, "schedule": CUSTOM}


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


@pytest.mark.parametrize("firewall_policy_payload", [[CUSTOM_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.DATE]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("firewall_policy_payload", [[CUSTOM_POLICY]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_schedule_dates_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The schedule dates are created disabled."""
    for entity_id in (START, END):
        assert hass.states.get(entity_id) is None
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("firewall_policy_payload", "start", "end"),
    [
        ([ONE_TIME_POLICY], "2026-01-15", STATE_UNKNOWN),
        ([CUSTOM_POLICY], "2026-01-05", "2026-01-30"),
        ([FIREWALL_POLICY], STATE_UNKNOWN, STATE_UNKNOWN),
        ([_policy({"mode": "ALWAYS"})], STATE_UNKNOWN, STATE_UNKNOWN),
        ([_policy({**ONE_TIME, "date": "2026-13-01"})], STATE_UNKNOWN, STATE_UNKNOWN),
        ([_policy(None)], STATE_UNKNOWN, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_schedule_date_values(hass: HomeAssistant, start: str, end: str) -> None:
    """The dates show what the schedule's mode uses."""
    assert hass.states.get(START).state == start
    assert hass.states.get(END).state == end


@pytest.mark.parametrize(
    ("firewall_policy_payload", "entity_id", "value", "expected_schedule"),
    [
        ([ONE_TIME_POLICY], START, "2026-02-01", {**ONE_TIME, "date": "2026-02-01"}),
        ([CUSTOM_POLICY], START, "2026-01-10", {**CUSTOM, "date_start": "2026-01-10"}),
        ([CUSTOM_POLICY], END, "2026-02-28", {**CUSTOM, "date_end": "2026-02-28"}),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_schedule_date(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    firewall_policy_payload: list[dict[str, Any]],
    entity_id: str,
    value: str,
    expected_schedule: dict[str, Any],
) -> None:
    """Setting a date sends the whole schedule with that date changed."""
    expected = {**firewall_policy_payload[0], "schedule": expected_schedule}
    _mock_put(aioclient_mock, config_entry_setup, expected)
    call_count = aioclient_mock.call_count

    await hass.services.async_call(
        DATE_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_DATE: value},
        blocking=True,
    )

    assert aioclient_mock.mock_calls[call_count][0] == "put"
    assert aioclient_mock.mock_calls[call_count][2] == expected


@pytest.mark.parametrize(
    ("firewall_policy_payload", "entity_id"),
    [
        ([FIREWALL_POLICY], START),
        ([FIREWALL_POLICY], END),
        ([ONE_TIME_POLICY], END),
        ([_policy({"mode": "ALWAYS"})], START),
        ([_policy({"mode": "SUNRISE"})], START),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_set_schedule_date_unused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, entity_id: str
) -> None:
    """A date can't be set in a mode that doesn't use it."""
    call_count = aioclient_mock.call_count
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DATE_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_DATE: "2026-02-01"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "schedule_setting_unused_in_mode"
    assert aioclient_mock.call_count == call_count


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        (START, "2026-01-31"),
        (END, "2026-01-04"),
        # The controller rejects a range that starts and ends on the same day.
        (START, "2026-01-30"),
        (END, "2026-01-05"),
    ],
)
@pytest.mark.parametrize("firewall_policy_payload", [[CUSTOM_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "config_entry_setup")
async def test_set_schedule_date_out_of_order(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    value: str,
) -> None:
    """A Custom range can't end before it starts."""
    call_count = aioclient_mock.call_count
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DATE_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_DATE: value},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "schedule_dates_out_of_order"
    assert aioclient_mock.call_count == call_count


@pytest.mark.parametrize("firewall_policy_payload", [[ONE_TIME_POLICY]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_schedule_date_request_failed(
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
            DATE_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: START, ATTR_DATE: "2026-02-01"},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "action_request_failed"
    assert hass.states.get(START).state == "2026-01-15"
