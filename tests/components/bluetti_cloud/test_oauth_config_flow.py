"""Tests for the OAuth2 device-binding config flow step (config_flow.py)."""

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


def _mock_product_client(products: list[UserProduct]):
    """Patch config_flow.ProductClient, returning products and a successful bind."""
    patcher = patch("homeassistant.components.bluetti_cloud.config_flow.ProductClient")
    mock_client_cls = patcher.start()
    mock_client_cls.return_value.get_user_products = AsyncMock(
        return_value=SimpleNamespace(data=products, is_ok=lambda: True)
    )
    mock_client_cls.return_value.bind_devices = AsyncMock(
        return_value=UnifyResponse(msgId="1", msgCode=0)
    )
    return patcher, mock_client_cls


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


async def test_new_entry_binds_every_account_device(hass: HomeAssistant) -> None:
    """Batteries included: every product on the account is bound and added."""
    flow = _make_flow(hass)
    products = [
        UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
        UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
    ]
    patcher, mock_client_cls = _mock_product_client(products)

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "create_entry"
    assert result["data"]["device_sns"] == ["SN1", "SN2"]
    assert "products" not in result["data"]
    mock_client_cls.return_value.bind_devices.assert_awaited_once_with(
        {"bindSnList": ["SN1", "SN2"]}
    )


async def test_new_entry_gets_account_unique_id(hass: HomeAssistant) -> None:
    """New entry gets account unique id."""
    flow = _make_flow(hass)
    products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    patcher, _mock_client_cls = _mock_product_client(products)

    try:
        await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert flow.unique_id == ACCOUNT_UNIQUE_ID


async def test_legacy_entry_without_unique_id_is_adopted(hass: HomeAssistant) -> None:
    """Entries created before ACCOUNT_UNIQUE_ID existed must still be found."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        title=f"{INTEGRATION_NAME} Power Integration",
    )
    legacy_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    products = [UserProduct(sn="SN1", name="New Device", stateList=[], online="1")]
    patcher, mock_client_cls = _mock_product_client(products)

    try:
        # A second account attempt (the legacy entry now carries the
        # account's unique_id) aborts rather than binding anything -
        # _abort_if_unique_id_configured() raises AbortFlow directly.
        with pytest.raises(AbortFlow) as exc_info:
            await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert exc_info.value.reason == "already_configured"
    mock_client_cls.return_value.bind_devices.assert_not_awaited()

    updated = hass.config_entries.async_get_entry(legacy_entry.entry_id)
    assert updated.unique_id == ACCOUNT_UNIQUE_ID


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
            "device_sns": ["SN0"],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    # _make_flow's flow.context == {} - self.source is None, matching a
    # real "Add Integration" flow (never reauth/reconfigure).
    products = [
        UserProduct(sn="SN1", name="Second Account Device", stateList=[], online="1")
    ]
    patcher, mock_client_cls = _mock_product_client(products)

    try:
        with pytest.raises(AbortFlow) as exc_info:
            await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert exc_info.value.reason == "already_configured"
    mock_client_cls.return_value.bind_devices.assert_not_awaited()

    # The first account's entry must be untouched - same token, same
    # devices, no second account's device merged in.
    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "original-token"}
    assert updated.data["device_sns"] == ["SN0"]


async def test_bind_devices_failure_aborts_cannot_connect(hass: HomeAssistant) -> None:
    """Bind devices failure aborts cannot connect."""
    flow = _make_flow(hass)
    products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    patcher, mock_client_cls = _mock_product_client(products)
    mock_client_cls.return_value.bind_devices.side_effect = RuntimeError("boom")

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

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
    products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    patcher, mock_client_cls = _mock_product_client(products)
    mock_client_cls.return_value.bind_devices = AsyncMock(
        return_value=UnifyResponse(msgId="1", msgCode=1)
    )

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failure_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Get user products failure aborts cannot connect."""
    flow = _make_flow(hass)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        result = await flow.async_step_select_devices()

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
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.async_get_clientsession"
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=805, data=None)
        )
        result = await flow.async_step_select_devices()

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_no_devices_available_aborts(hass: HomeAssistant) -> None:
    """No devices available aborts."""
    flow = _make_flow(hass)
    patcher, _mock_client_cls = _mock_product_client([])

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_reconfigure_token_updates_existing_entry(hass: HomeAssistant) -> None:
    """Re-running the flow for an existing entry_id refreshes the token and re-binds.

    Uses async_update_reload_and_abort - the framework's own helper for
    "persist this change and reload", rather than a hand-rolled
    update-listener the entry registers itself.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "device_sns": [],
        },
    )
    existing_entry.add_to_hass(hass)
    existing_entry.mock_state(hass, ConfigEntryState.LOADED)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    products = [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
    patcher, mock_client_cls = _mock_product_client(products)

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        try:
            result = await flow.async_step_select_devices()
        finally:
            patcher.stop()
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    mock_reload.assert_awaited_once_with(existing_entry.entry_id)
    mock_client_cls.return_value.bind_devices.assert_awaited_once_with(
        {"bindSnList": ["SN1"]}
    )

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}
    assert updated.data["device_sns"] == ["SN1"]


async def test_reconfigure_rebind_failure_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A bind failure while re-binding during reconfigure aborts, not just logs."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "device_sns": [],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    products = [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
    patcher, mock_client_cls = _mock_product_client(products)
    mock_client_cls.return_value.bind_devices.side_effect = RuntimeError("boom")

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "old"}


async def test_reconfigure_rebind_rejected_response_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A rejected bind (nonzero msgCode) while re-binding must not be treated as success."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "device_sns": [],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    products = [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
    patcher, mock_client_cls = _mock_product_client(products)
    mock_client_cls.return_value.bind_devices = AsyncMock(
        return_value=UnifyResponse(msgId="1", msgCode=1)
    )

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "old"}


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
            "device_sns": [],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    flow._oauth_data["auth_implementation"] = "new_credential"
    products = [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
    patcher, _mock_client_cls = _mock_product_client(products)

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["auth_implementation"] == "new_credential"


async def test_reconfigure_token_rejects_a_different_account(
    hass: HomeAssistant,
) -> None:
    """Reauthenticating with a different BLUETTI account must not replace the token.

    Regression test: ACCOUNT_UNIQUE_ID is a fixed constant, not derived
    per-account, so there was nothing stopping a reconfigure flow from
    silently overwriting an entry's token with a different account's -
    leaving the entry's already-bound devices permanently inaccessible
    (their serials belong to an account the new token can no longer query).
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "original-token"},
            "device_sns": ["SN0"],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    # The reauthenticated account doesn't have SN0 - a different account.
    other_account_product = UserProduct(
        sn="SN1", name="Unrelated Device", stateList=[], online="1"
    )
    patcher, mock_client_cls = _mock_product_client([other_account_product])

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        try:
            result = await flow.async_step_select_devices()
        finally:
            patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "wrong_account"
    mock_reload.assert_not_awaited()
    mock_client_cls.return_value.bind_devices.assert_not_awaited()

    # The entry must be untouched - same token as before.
    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "original-token"}


async def test_reconfigure_token_accepts_partial_device_overlap(
    hass: HomeAssistant,
) -> None:
    """Reauthenticating the same account after an offline unbind must succeed.

    Regression test: the wrong-account check used to require every
    previously-bound device to still be present, so a device unbound from
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
            "device_sns": ["SN0", "SN1"],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    # SN1 was unbound from the cloud - only SN0 comes back now.
    same_account_product = UserProduct(
        sn="SN0", name="Existing", stateList=[], online="1"
    )
    patcher, _mock_client_cls = _mock_product_client([same_account_product])

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}
    assert updated.data["device_sns"] == ["SN0"]


async def test_reconfigure_token_with_zero_devices_on_account_still_succeeds(
    hass: HomeAssistant,
) -> None:
    """Reauth must not require a non-empty product list.

    Regression test: no_devices_available used to be checked before the
    reconfigure-token branch, so an entry with no devices currently bound
    (e.g. all removed) could never complete reauthentication - it always
    hit no_devices_available first.
    """
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={
            "auth_implementation": "bluetti_cloud",
            "token": {"access_token": "old"},
            "device_sns": [],
        },
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": existing_entry.entry_id}
    patcher, _mock_client_cls = _mock_product_client([])

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}


async def test_reconfigure_token_missing_entry_aborts(hass: HomeAssistant) -> None:
    """entry_id in context but the entry itself is gone (e.g. removed mid-flow)."""
    flow = _make_flow(hass)
    flow.context = {"entry_id": "does-not-exist"}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")
    patcher, _mock_client_cls = _mock_product_client([product])

    try:
        result = await flow.async_step_select_devices()
    finally:
        patcher.stop()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"
