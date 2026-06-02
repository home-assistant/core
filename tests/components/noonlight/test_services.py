"""Service registration and handler tests."""

from __future__ import annotations

import json

from httpx import Response
import pytest
import respx

from homeassistant.components.noonlight.const import (
    ALL_NOONLIGHT_SERVICES,
    CONF_API_TOKEN,
    CONF_DEDUPE_SECONDS,
    CONF_DEFAULT_ENTRY_DELAY,
    CONF_ENVIRONMENT,
    CONF_LOCATION_ID,
    CONF_SERVICES_GRANTED,
    DOMAIN,
    ENV_SANDBOX,
    STATE_DISPATCHED,
    SVC_CANCEL,
    SVC_DISPATCH_ALL,
    SVC_DISPATCH_FIRE,
    SVC_DISPATCH_MEDICAL,
    SVC_DISPATCH_POLICE,
    SVC_TEST_DISPATCH,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import SANDBOX

from tests.common import MockConfigEntry

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"


def _coordinator(hass, entry):
    return hass.data[DOMAIN][entry.entry_id]


async def test_services_registered(hass, setup_entry):
    for service in (
        SVC_DISPATCH_POLICE,
        SVC_DISPATCH_FIRE,
        SVC_DISPATCH_MEDICAL,
        SVC_DISPATCH_ALL,
        SVC_CANCEL,
        SVC_TEST_DISPATCH,
    ):
        assert hass.services.has_service(DOMAIN, service)


async def test_services_removed_on_unload(hass, setup_entry):
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, SVC_DISPATCH_POLICE)


@respx.mock
async def test_dispatch_police_service(hass, setup_entry):
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    await hass.services.async_call(
        DOMAIN,
        SVC_DISPATCH_POLICE,
        {"entry_delay_seconds": 0},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert create.called
    state = hass.states.get("sensor.noonlight_main_dispatch_state")
    assert state.state == "dispatched"


@respx.mock
async def test_dispatch_includes_site_owner_id_and_combined_instructions(hass):
    """An entry with a location label sends owner_id and folds the site into
    the responder instructions.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Site A",
        entry_id="sitea",
        data={
            CONF_API_TOKEN: "t",
            CONF_ENVIRONMENT: ENV_SANDBOX,
            "name": "Owner",
            "phone": "+15555550123",
            "address": "1 St",
            "city": "C",
            "state": "CA",
            "zip": "90001",
            CONF_LOCATION_ID: "Site A",
        },
        options={
            CONF_DEFAULT_ENTRY_DELAY: 30,
            CONF_DEDUPE_SECONDS: 300,
            CONF_SERVICES_GRANTED: ALL_NOONLIGHT_SERVICES,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "a", "status": "ACTIVE"})
    )

    await hass.services.async_call(
        DOMAIN,
        SVC_DISPATCH_POLICE,
        {"entry_delay_seconds": 0, "instructions": "Front Door motion"},
        blocking=True,
    )
    await hass.async_block_till_done()

    payload = json.loads(create.calls.last.request.content)
    assert payload["owner_id"] == "Site A"
    assert payload["instructions"] == {"entry": "Site A — Front Door motion"}


@respx.mock
async def test_dispatch_passes_instructions_to_noonlight(hass, setup_entry):
    """The instructions field reaches Noonlight's instructions.entry."""
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    await hass.services.async_call(
        DOMAIN,
        SVC_DISPATCH_POLICE,
        {"entry_delay_seconds": 0, "instructions": "Front Door motion"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert create.called
    payload = json.loads(create.calls.last.request.content)
    assert payload["instructions"] == {"entry": "Front Door motion"}


async def test_dispatch_ungranted_service_raises(hass, setup_entry):
    """Calling a dispatch service that isn't granted is rejected."""
    hass.config_entries.async_update_entry(
        setup_entry, options={CONF_SERVICES_GRANTED: ["fire"]}
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SVC_DISPATCH_POLICE,
            {"entry_delay_seconds": 0},
            blocking=True,
        )


@respx.mock
async def test_cancel_service_cancels_pending(hass, setup_entry):
    """The HA cancel service reaches the coordinator and cancels a dispatch."""
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )
    # Pending dispatch (long delay) that we then cancel via the service.
    coordinator = _coordinator(hass, setup_entry)
    await coordinator.async_dispatch(["police"], 60)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SVC_CANCEL, {"reason": "disarmed"}, blocking=True
    )
    await hass.async_block_till_done()

    assert coordinator.data["state"] == "canceled"


async def test_unknown_account_raises(hass, setup_entry):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SVC_CANCEL,
            {"account": "does-not-exist"},
            blocking=True,
        )


@respx.mock
async def test_test_dispatch_hits_sandbox(hass, setup_entry):
    """test_dispatch creates and immediately cancels a sandbox alarm."""
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "sandbox-1", "status": "ACTIVE"})
    )
    cancel = respx.route(
        method="POST", url__regex=r".*/dispatch/v1/alarms/.*/status"
    ).mock(return_value=Response(200, json={"status": "CANCELED"}))

    await hass.services.async_call(DOMAIN, SVC_TEST_DISPATCH, {}, blocking=True)
    await hass.async_block_till_done()

    assert create.called
    assert cancel.called
    # The live state machine is untouched by a test dispatch.
    assert hass.states.get("sensor.noonlight_main_dispatch_state").state == "idle"


@respx.mock
async def test_test_dispatch_failure_raises_ha_error(hass, setup_entry):
    """A failed sandbox round-trip surfaces as a HomeAssistantError."""
    respx.post(_ALARMS).mock(return_value=Response(500, text="boom"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SVC_TEST_DISPATCH, {}, blocking=True)


@respx.mock
async def test_dispatch_all_limited_to_granted_services(hass, setup_entry):
    """dispatch_all with only police granted fires police alone."""
    hass.config_entries.async_update_entry(
        setup_entry, options={CONF_SERVICES_GRANTED: ["police"]}
    )
    await hass.async_block_till_done()
    create = respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "abc123", "status": "ACTIVE"})
    )

    await hass.services.async_call(
        DOMAIN, SVC_DISPATCH_ALL, {"entry_delay_seconds": 0}, blocking=True
    )
    await hass.async_block_till_done()

    assert create.called
    coordinator = _coordinator(hass, setup_entry)
    assert coordinator.data["state"] == STATE_DISPATCHED
    assert coordinator.data["services"] == ["police"]
    # Only police was requested of Noonlight.
    services = json.loads(create.calls.last.request.content)["services"]
    assert services == {"police": True}


def _second_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Second",
        entry_id="noonlight2",
        data={
            CONF_API_TOKEN: "tok2",
            CONF_ENVIRONMENT: ENV_SANDBOX,
            "name": "Second",
            "phone": "+15555550199",
            "address": "2 Test Ave",
            "city": "Testville",
            "state": "CA",
            "zip": "90002",
        },
        options={
            CONF_DEFAULT_ENTRY_DELAY: 30,
            CONF_DEDUPE_SECONDS: 300,
            CONF_SERVICES_GRANTED: ALL_NOONLIGHT_SERVICES,
        },
    )


async def test_multiple_accounts_require_account_arg(hass, setup_entry):
    """With >1 entry, omitting 'account' is rejected."""
    second = _second_entry()
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SVC_DISPATCH_POLICE,
            {"entry_delay_seconds": 0},
            blocking=True,
        )


@respx.mock
async def test_account_selected_by_title(hass, setup_entry):
    """The 'account' arg resolves by human-readable title."""
    second = _second_entry()
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    respx.post(_ALARMS).mock(
        return_value=Response(201, json={"id": "z9", "status": "ACTIVE"})
    )

    await hass.services.async_call(
        DOMAIN,
        SVC_DISPATCH_POLICE,
        {"entry_delay_seconds": 0, "account": "Second"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _coordinator(hass, second).data["state"] == STATE_DISPATCHED
    # The first account stayed idle.
    assert _coordinator(hass, setup_entry).data["state"] == "idle"
