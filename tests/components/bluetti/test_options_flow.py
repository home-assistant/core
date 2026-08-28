"""Tests for the BLUETTI options flow (add devices without re-authenticating)."""

from contextlib import contextmanager
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pybluetti import UnifyResponse, UserProduct

from homeassistant.components.bluetti.config_flow import BluettiConfigFlow
from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.components.bluetti.options_flow import BluettiOptionsFlowHandler
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import JSONEncoder

from tests.common import MockConfigEntry


def _flow(hass: HomeAssistant, entry) -> BluettiOptionsFlowHandler:
    flow = BluettiOptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id
    return flow


@contextmanager
def _patched_oauth():
    """Patch the options flow's OAuth2Session-backed token refresh."""
    with (
        patch(
            "homeassistant.components.bluetti.options_flow.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.options_flow.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
    ):
        mock_session_cls.return_value.token = {"access_token": "tok"}
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        yield mock_session_cls


def _entry(hass: HomeAssistant, *, products=None, devices=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok"},
            "products": products or [],
        },
        options={"devices": devices or []},
    )
    entry.add_to_hass(hass)
    return entry


async def test_shows_form_with_available_devices(hass: HomeAssistant) -> None:
    """Shows form with available devices."""
    entry = _entry(hass, devices=["SN1"])
    flow = _flow(hass, entry)
    products = [
        UserProduct(sn="SN1", name="Already added", stateList=[], online="1"),
        UserProduct(sn="SN2", name="New device", stateList=[], online="1"),
    ]

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=products, is_ok=lambda: True)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_no_devices_available_aborts(hass: HomeAssistant) -> None:
    """No devices available aborts."""
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[], is_ok=lambda: True)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_all_devices_already_enabled_aborts(hass: HomeAssistant) -> None:
    """All devices already enabled aborts."""
    entry = _entry(hass, devices=["SN1"])
    flow = _flow(hass, entry)
    products = [UserProduct(sn="SN1", name="Already added", stateList=[], online="1")]

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=products, is_ok=lambda: True)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "all_devices_exists"


async def test_fetch_failure_aborts_cannot_connect(hass: HomeAssistant) -> None:
    """Fetch failure aborts cannot connect."""
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failed_envelope_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A failed application-level response must not look like "no devices".

    Regression test: get_user_products() doesn't raise for a nonzero
    msgCode - it returns a UnifyResponse with data=None. Previously this
    fell through to no_devices_available instead of cannot_connect.
    """
    entry = _entry(hass)
    flow = _flow(hass, entry)

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=805, data=None)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_submit_binds_and_merges_devices_and_products(
    hass: HomeAssistant,
) -> None:
    """Submit binds and merges devices and products."""
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Existing", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=0)
    flow._products = [
        UserProduct(sn="SN2", name="New Device", stateList=[], online="1")
    ]

    result = await flow.async_step_init(user_input={"devices": ["SN2"]})

    assert result["type"] == "create_entry"
    assert set(result["data"]["devices"]) == {"SN1", "SN2"}
    flow._product_client.bind_devices.assert_awaited_once_with({"bindSnList": ["SN2"]})

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    stored_sns = {p["sn"] for p in updated.data["products"]}
    assert stored_sns == {"SN1", "SN2"}
    json.dumps(dict(updated.data), cls=JSONEncoder)  # must stay JSON-serializable


async def test_submit_bind_failure_aborts_cannot_connect(hass: HomeAssistant) -> None:
    """Submit bind failure aborts cannot connect."""
    entry = _entry(hass)
    flow = _flow(hass, entry)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.side_effect = RuntimeError("boom")

    result = await flow.async_step_init(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_submit_bind_rejected_response_aborts_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """A rejected bind (nonzero msgCode) must not be treated as success.

    Regression test: bind_devices() returns UnifyResponse | str and does not
    raise on a rejected bind - previously this fell through and persisted
    the devices as though binding succeeded.
    """
    entry = _entry(hass)
    flow = _flow(hass, entry)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.return_value = UnifyResponse(msgId="1", msgCode=1)

    result = await flow.async_step_init(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_config_flow_exposes_options_flow(hass: HomeAssistant) -> None:
    """Config flow exposes options flow."""
    entry = _entry(hass)
    flow = BluettiConfigFlow.async_get_options_flow(entry)

    assert isinstance(flow, BluettiOptionsFlowHandler)


async def test_add_devices_through_real_flow_manager_reloads_exactly_once(
    hass: HomeAssistant,
) -> None:
    """Adding devices through the real options flow must reload the entry once.

    Regression test: async_step_init used to call async_update_entry()
    twice for one "add devices" submission - once directly for
    entry.data["products"], once indirectly via OptionsFlowManager's own
    async_update_entry(entry, options=result["data"]) when finishing the
    flow - each firing this entry's _async_update_listener (registered on
    it here, matching a real loaded entry) and reloading it.
    entry.setup_lock serializes these rather than corrupting anything, but
    the entry would still fully unload+setup twice for one "add devices"
    action.
    """
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Existing", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    entry.add_update_listener(
        lambda hass, entry: hass.config_entries.async_reload(entry.entry_id)
    )

    products = [UserProduct(sn="SN2", name="New Device", stateList=[], online="1")]
    reload_calls = []

    async def _fake_reload(entry_id: str) -> bool:
        reload_calls.append(entry_id)
        return True

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
        patch.object(hass.config_entries, "async_reload", _fake_reload),
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=products, is_ok=lambda: True)
        )
        mock_client_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "form"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"devices": ["SN2"]}
        )

    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    assert reload_calls == [entry.entry_id]
