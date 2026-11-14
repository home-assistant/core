"""Common methods used across tests for Netatmo."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
from typing import Any
from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMockResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.netatmo.const import DOMAIN
from homeassistant.components.webhook import async_handle_webhook
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.aiohttp import MockRequest

HOME_ID = "91763b24c43d3e344f424e8b"
SCHEDULE_SELECT_UNIQUE_ID = f"{HOME_ID}-schedule-select"
LEGACY_CLIMATE_ISSUE_ID = f"legacy_climate_device_disabled_{HOME_ID}"

COMMON_RESPONSE = {
    "user_id": "91763b24c43d3e344f424e8d",
    "home_id": HOME_ID,
    "home_name": "MYHOME",
    "user": {"id": HOME_ID, "email": "john@doe.com"},
}

FAKE_WEBHOOK_ACTIVATION = {
    "push_type": "webhook_activation",
}


async def snapshot_platform_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platform: Platform,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot entities and their states."""
    with selected_platforms([platform]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


async def fake_post_request(hass: HomeAssistant, *args: Any, **kwargs: Any):
    """Return fake data."""
    if "endpoint" not in kwargs:
        return "{}"

    endpoint = kwargs["endpoint"].split("/")[-1]

    if endpoint in "snapshot_720.jpg":
        return b"test stream image bytes"

    if endpoint in [
        "setpersonsaway",
        "setpersonshome",
        "setstate",
        "setroomthermpoint",
        "setthermmode",
        "switchhomeschedule",
    ]:
        payload = {f"{endpoint}": True, "status": "ok"}

    elif endpoint == "homestatus":
        home_id = kwargs.get("params", {}).get("home_id")
        payload = await async_load_json_object_fixture(
            hass, f"{endpoint}_{home_id}.json", DOMAIN
        )

    else:
        payload = await async_load_json_object_fixture(hass, f"{endpoint}.json", DOMAIN)

    # Apply test-specific modifications to the payload
    if "msg_callback" in kwargs:
        kwargs["msg_callback"](payload)

    return AiohttpClientMockResponse(
        method="POST",
        url=kwargs["endpoint"],
        json=payload,
    )


async def fake_get_image(*args: Any, **kwargs: Any) -> bytes | str | None:
    """Return fake data."""
    if "endpoint" not in kwargs:
        return "{}"

    endpoint = kwargs["endpoint"].split("/")[-1]

    if endpoint in "snapshot_720.jpg":
        return b"test stream image bytes"
    return None


async def simulate_webhook(hass: HomeAssistant, webhook_id: str, response) -> None:
    """Simulate a webhook event."""
    request = MockRequest(
        method="POST",
        content=bytes(json.dumps({**COMMON_RESPONSE, **response}), "utf-8"),
        mock_source="test",
    )
    await async_handle_webhook(hass, webhook_id, request)
    await hass.async_block_till_done()


@contextmanager
def selected_platforms(platforms: list[Platform]) -> Iterator[None]:
    """Restrict loaded platforms to list given."""
    with (
        patch("homeassistant.components.netatmo.coordinator.PLATFORMS", platforms),
        patch(
            "homeassistant.components.netatmo.async_get_config_entry_implementation",
        ),
        patch(
            "homeassistant.components.netatmo.webhook.webhook_generate_url",
        ),
    ):
        yield


def add_disabled_home_with_schedule_select(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    model: str,
) -> tuple[dr.DeviceEntry, er.RegistryEntry]:
    """Register a disabled device for HOME_ID with the schedule select on it.

    With model "Climate" this is the pre-2026.9 device, which only carried the
    select. With model "Home" it is the same device after 2026.9 renamed it.
    """
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, HOME_ID)},
        model=model,
        name="MYHOME",
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    entity = entity_registry.async_get_or_create(
        Platform.SELECT,
        DOMAIN,
        SCHEDULE_SELECT_UNIQUE_ID,
        config_entry=config_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.DEVICE,
    )
    return device, entity
