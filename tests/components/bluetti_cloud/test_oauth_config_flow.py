"""Tests for the OAuth2 device-selection config flow step (config_flow.py)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pybluetti import UnifyResponse, UserProduct
import pytest

from homeassistant.components.bluetti_cloud.config_flow import BluettiConfigFlow
from homeassistant.components.bluetti_cloud.const import (
    ACCOUNT_UNIQUE_ID,
    DOMAIN,
    INTEGRATION_NAME,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.json import JSONEncoder

from tests.common import MockConfigEntry


def _make_flow(hass: HomeAssistant) -> BluettiConfigFlow:
    flow = BluettiConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.context = {}
    flow._oauth_data = {
        "auth_implementation": "bluetti_cloud",
        "token": {"access_token": "tok", "expires_at": 9999999999},
    }
    return flow


async def test_async_step_reconfigure_delegates_to_oauth_handler(
    hass: HomeAssistant,
) -> None:
    """Must actually delegate, not just exist as a stub for hassfest."""
    flow = _make_flow(hass)
    flow.context = {"entry_id": "does-not-exist"}

    result = await flow.async_step_reconfigure()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"


async def test_async_step_reauth_delegates_to_confirm(hass: HomeAssistant) -> None:
    """Async step reauth delegates to the confirm step."""
    flow = _make_flow(hass)
    flow.async_step_reauth_confirm = AsyncMock(return_value={"type": "form"})

    result = await flow.async_step_reauth({})

    flow.async_step_reauth_confirm.assert_awaited_once_with()
    assert result == {"type": "form"}


async def test_async_step_reauth_confirm_shows_form_when_no_input(
    hass: HomeAssistant,
) -> None:
    """Async step reauth confirm shows form when no input."""
    flow = _make_flow(hass)

    result = await flow.async_step_reauth_confirm()

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"


async def test_async_step_reauth_confirm_delegates_to_user_step_when_confirmed(
    hass: HomeAssistant,
) -> None:
    """Async step reauth confirm delegates to user step when confirmed."""
    flow = _make_flow(hass)
    flow.async_step_user = AsyncMock(return_value={"type": "abort"})

    result = await flow.async_step_reauth_confirm(user_input={})

    flow.async_step_user.assert_awaited_once_with()
    assert result == {"type": "abort"}


async def test_new_entry_products_are_json_serializable(hass: HomeAssistant) -> None:
    """New entry products are json serializable."""
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "create_entry"
    stored_products = result["data"]["products"]
    assert all(isinstance(p, dict) for p in stored_products)
    # Must not raise: this is what Home Assistant does to persist the entry.
    json.dumps(result["data"], cls=JSONEncoder)


async def test_new_entry_only_caches_selected_products(hass: HomeAssistant) -> None:
    """New entry only caches selected products.

    Regression test: entry.data["products"] used to cache every product on
    the account, not just the ones the user actually selected. A device
    left unselected here (SN2) would then, when added later via the
    options flow, look like it was "already cached" and reuse this stale
    snapshot instead of a fresh get_user_products() fetch.
    """
    flow = _make_flow(hass)
    flow._products = [
        UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
        UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "create_entry"
    stored_sns = {p["sn"] for p in result["data"]["products"]}
    assert stored_sns == {"SN1"}


async def test_new_entry_gets_account_unique_id(hass: HomeAssistant) -> None:
    """New entry gets account unique id."""
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert flow.unique_id == ACCOUNT_UNIQUE_ID


async def test_merge_into_existing_entry_only_caches_selected_products(
    hass: HomeAssistant,
) -> None:
    """Merging into an existing entry only caches selected products.

    Same regression as test_new_entry_only_caches_selected_products, but
    for the merge branch (reconfigure/reauth re-run finding an existing
    entry) rather than fresh entry creation.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "products": [
                {"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}
            ]
        },
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context["source"] = SOURCE_RECONFIGURE
    flow._products = [
        UserProduct(sn="SN1", name="New Device", stateList=[], online="1"),
        UserProduct(sn="SN2", name="Not Selected", stateList=[], online="1"),
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    with pytest.raises(AbortFlow):
        await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    stored_sns = {p["sn"] for p in updated.data["products"]}
    assert stored_sns == {"SN0", "SN1"}


async def test_merge_into_existing_entry_by_unique_id(hass: HomeAssistant) -> None:
    """Merge into existing entry by unique id."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "products": [
                {"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}
            ]
        },
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    # A plain fresh flow finding an existing entry aborts as
    # already_configured instead of merging (see the reason for that in
    # config_flow.py) - this test is specifically about the reconfigure/
    # reauth re-run path, which is the only one allowed to merge/update.
    flow.context["source"] = SOURCE_RECONFIGURE
    flow._products = [
        UserProduct(sn="SN1", name="New Device", stateList=[], online="1")
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    # _abort_if_unique_id_configured() raises AbortFlow directly (the real
    # flow manager catches this and turns it into the {"type": "abort", ...}
    # result seen by a user going through a real flow). It only schedules a
    # reload for an entry already LOADED/SETUP_RETRY, which this bare
    # MockConfigEntry - added but never actually set up - isn't, so there's
    # nothing to assert about reload scheduling here; the merge is the
    # behavior under test.
    with pytest.raises(AbortFlow) as exc_info:
        await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert exc_info.value.reason == "success"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert set(updated.options["devices"]) == {"SN0", "SN1"}
    stored_sns = {p["sn"] for p in updated.data["products"]}
    assert stored_sns == {"SN0", "SN1"}
    # Must not raise: this is what Home Assistant does to persist the entry.
    json.dumps(dict(updated.data), cls=JSONEncoder)


async def test_merge_into_existing_entry_reloads_exactly_once(
    hass: HomeAssistant,
) -> None:
    """Merging into a LOADED entry must reload it exactly once, not three times.

    Regression test: the merge branch used to call async_update_entry()
    twice for one merge - once directly for options={"devices": ...}, once
    indirectly via _abort_if_unique_id_configured()'s own data= update for
    the token/products - each firing this entry's _async_update_listener
    (registered on it, matching a real loaded entry) and reloading it, plus
    a third explicit reload from _abort_if_unique_id_configured's own
    reload_on_update=True (which only schedules one when the entry is
    LOADED/SETUP_RETRY - hence mock_state below). entry.setup_lock
    serializes these rather than corrupting anything, but the entry would
    still fully unload+setup three times for one merge.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "original-token"},
            "products": [
                {"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}
            ],
        },
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)
    existing_entry.mock_state(hass, ConfigEntryState.LOADED)

    reload_calls = []

    async def _fake_reload(entry_id: str) -> bool:
        reload_calls.append(entry_id)
        return True

    existing_entry.add_update_listener(
        lambda hass, entry: hass.config_entries.async_reload(entry.entry_id)
    )

    flow = _make_flow(hass)
    flow.context["source"] = SOURCE_RECONFIGURE
    flow._products = [
        UserProduct(sn="SN1", name="New Device", stateList=[], online="1")
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    with (
        patch.object(hass.config_entries, "async_reload", _fake_reload),
        pytest.raises(AbortFlow) as exc_info,
    ):
        await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert exc_info.value.reason == "success"
    await hass.async_block_till_done()

    assert reload_calls == [existing_entry.entry_id]


async def test_legacy_entry_without_unique_id_is_adopted(hass: HomeAssistant) -> None:
    """Entries created before ACCOUNT_UNIQUE_ID existed must still be found."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"products": []},
        options={"devices": []},
    )
    legacy_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context["source"] = SOURCE_RECONFIGURE
    flow._products = [
        UserProduct(sn="SN1", name="New Device", stateList=[], online="1")
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    with (
        patch.object(hass.config_entries, "async_schedule_reload"),
        pytest.raises(AbortFlow) as exc_info,
    ):
        await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert exc_info.value.reason == "success"

    updated = hass.config_entries.async_get_entry(legacy_entry.entry_id)
    assert updated.unique_id == ACCOUNT_UNIQUE_ID
    assert updated.options["devices"] == ["SN1"]


async def test_second_account_via_fresh_flow_aborts_already_configured(
    hass: HomeAssistant,
) -> None:
    """A plain (non-reauth/reconfigure) flow rejects a second account.

    Regression test: authenticating a different BLUETTI account through a
    fresh "Add Integration" flow while one is already configured used to
    merge into the existing entry and overwrite its stored token with the
    second account's - leaving the first account's retained devices
    inaccessible. It must instead abort cleanly and leave the existing
    entry untouched.

    It must also reject before calling bind_devices() at all - otherwise a
    rejected setup still performs a real, wasted cloud-side bind that Home
    Assistant then discards locally.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "original-token"},
            "products": [
                {"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}
            ],
        },
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    # _make_flow's flow.context == {} - self.source is None, matching a
    # real "Add Integration" flow (never reauth/reconfigure).
    flow._products = [
        UserProduct(sn="SN1", name="Second Account Device", stateList=[], online="1")
    ]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    flow._product_client.bind_devices.assert_not_awaited()

    # The first account's entry must be untouched - same token, same
    # devices, no second account's device merged in.
    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "original-token"}
    assert updated.options["devices"] == ["SN0"]


async def test_bind_devices_failure_aborts_cannot_connect(hass: HomeAssistant) -> None:
    """Bind devices failure aborts cannot connect."""
    flow = _make_flow(hass)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.side_effect = RuntimeError("boom")

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_bind_devices_rejected_response_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A rejected bind (nonzero msgCode) must not be treated as success.

    Regression test: bind_devices() returns UnifyResponse | str and does not
    raise on a rejected bind - previously this fell through and created the
    entry as though the devices were actually bound.
    """
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=1)

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failure_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Get user products failure aborts cannot connect."""
    flow = _make_flow(hass)

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failed_envelope_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A failed application-level response must not look like "no devices".

    Regression test: get_user_products() doesn't raise for a nonzero
    msgCode (e.g. an expired token) - it returns a UnifyResponse with
    data=None. Previously this fell through to no_devices_available,
    misleading the user, instead of cannot_connect.
    """
    flow = _make_flow(hass)

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=805, data=None)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_no_devices_available_aborts(hass: HomeAssistant) -> None:
    """No devices available aborts."""
    flow = _make_flow(hass)

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_all_devices_exists_aborts(hass: HomeAssistant) -> None:
    """All devices exists aborts."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"products": []},
        options={"devices": ["SN1"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    product = UserProduct(sn="SN1", name="Already Added", stateList=[], online="1")

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "all_devices_exists"


async def test_reconfigure_token_updates_existing_entry(hass: HomeAssistant) -> None:
    """Re-running the flow for an existing entry_id refreshes the token.

    Regression test: the reload used to be an explicit call after
    async_update_entry() - on a loaded entry (mock_state below), that
    update already fires the registered update listener, which reloads -
    the explicit call was a second, redundant reload.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "products": [],
        },
        options={"devices": []},
    )
    existing_entry.add_to_hass(hass)
    existing_entry.mock_state(hass, ConfigEntryState.LOADED)
    existing_entry.add_update_listener(
        lambda hass, entry: hass.config_entries.async_reload(entry.entry_id)
    )

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "success"
    mock_reload.assert_awaited_once_with(existing_entry.entry_id)

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}


async def test_reconfigure_token_updates_auth_implementation_too(
    hass: HomeAssistant,
) -> None:
    """A different Application Credential picked during reconfigure must stick.

    Regression test: only "token" was persisted on reconfigure, silently
    keeping the old auth_implementation even if the user picked a
    different Application Credential during this OAuth login - later
    token refreshes would then use the wrong credentials.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "old_credential",
            "token": {"access_token": "old"},
            "products": [],
        },
        options={"devices": []},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}
    flow._oauth_data["auth_implementation"] = "new_credential"
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["auth_implementation"] == "new_credential"


async def test_reconfigure_token_rejects_a_different_account(
    hass: HomeAssistant,
) -> None:
    """Reauthenticating with a different BLUETTI account must not replace the token.

    Regression test: ACCOUNT_UNIQUE_ID is a fixed constant, not derived
    per-account, so there was nothing stopping a reconfigure flow from
    silently overwriting an entry's token with a different account's -
    leaving the entry's already-enabled devices permanently inaccessible
    (their serials belong to an account the new token can no longer query).
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "original-token"},
            "products": [{"sn": "SN0", "name": "Existing", "stateList": []}],
        },
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}
    # The reauthenticated account doesn't have SN0 - a different account.
    other_account_product = UserProduct(
        sn="SN1", name="Unrelated Device", stateList=[], online="1"
    )

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(
                data=[other_account_product], is_ok=lambda: True
            )
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "wrong_account"
    mock_reload.assert_not_awaited()

    # The entry must be untouched - same token as before.
    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "original-token"}


async def test_reconfigure_token_accepts_partial_device_overlap(
    hass: HomeAssistant,
) -> None:
    """Reauthenticating the same account after an offline unbind must succeed.

    Regression test: the wrong-account check used to require every
    already-enabled device to still be present, so a device unbound from
    the cloud while this entry's token was expired (meaning the normal
    unbind detection never ran to drop it locally) permanently blocked
    reauthenticating the very account that could fix it. Any overlap is
    now enough - the still-missing device is cleaned up normally by the
    next refresh's unbind detection once reauth succeeds.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "products": [
                {"sn": "SN0", "name": "Existing", "stateList": []},
                {"sn": "SN1", "name": "Unbound while offline", "stateList": []},
            ],
        },
        options={"devices": ["SN0", "SN1"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}
    # SN1 was unbound from the cloud - only SN0 comes back now.
    same_account_product = UserProduct(
        sn="SN0", name="Existing", stateList=[], online="1"
    )

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(
                data=[same_account_product], is_ok=lambda: True
            )
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}


async def test_reconfigure_token_with_zero_devices_on_account_still_succeeds(
    hass: HomeAssistant,
) -> None:
    """Reauth must not require a non-empty product list.

    Regression test: no_devices_available used to be checked before the
    reconfigure-token branch, so an entry with no devices currently
    enabled (e.g. all removed) could never complete reauthentication - it
    always hit no_devices_available first.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "products": [],
        },
        options={"devices": []},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}


async def test_reconfigure_token_missing_entry_aborts(hass: HomeAssistant) -> None:
    """entry_id in context but the entry itself is gone (e.g. removed mid-flow)."""
    flow = _make_flow(hass)
    flow.context = {"entry_id": "does-not-exist"}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with (
        patch("homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product], is_ok=lambda: True)
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"
