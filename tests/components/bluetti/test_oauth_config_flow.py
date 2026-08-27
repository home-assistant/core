"""Tests for the OAuth2 device-selection config flow step (oauth.py)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pybluetti import UserProduct

from homeassistant.components.bluetti.const import (
    ACCOUNT_UNIQUE_ID,
    DOMAIN,
    INTEGRATION_NAME,
)
from homeassistant.components.bluetti.oauth import OAuth2FlowHandler
from homeassistant.helpers.json import JSONEncoder

from tests.common import MockConfigEntry


def _make_flow(hass) -> OAuth2FlowHandler:
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {}
    flow._oauth_data = {
        "auth_implementation": "bluetti",
        "token": {"access_token": "tok", "expires_at": 9999999999},
    }
    return flow


async def test_new_entry_products_are_json_serializable(hass):
    """New entry products are json serializable."""
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "create_entry"
    stored_products = result["data"]["products"]
    assert all(isinstance(p, dict) for p in stored_products)
    # Must not raise: this is what Home Assistant does to persist the entry.
    json.dumps(result["data"], cls=JSONEncoder)


async def test_new_entry_gets_account_unique_id(hass):
    """New entry gets account unique id."""
    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="Device 1", stateList=[], online="1")]
    flow._product_client = AsyncMock()

    await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert flow.unique_id == ACCOUNT_UNIQUE_ID


async def test_merge_into_existing_entry_by_unique_id(hass):
    """Merge into existing entry by unique id."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"products": [{"sn": "SN0", "name": "Existing", "stateList": [], "online": "1"}]},
        options={"devices": ["SN0"]},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow._products = [UserProduct(sn="SN1", name="New Device", stateList=[], online="1")]
    flow._product_client = AsyncMock()

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "success"
    mock_reload.assert_awaited_once_with(existing_entry.entry_id)

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert set(updated.options["devices"]) == {"SN0", "SN1"}
    stored_sns = {p["sn"] for p in updated.data["products"]}
    assert stored_sns == {"SN0", "SN1"}
    # Must not raise: this is what Home Assistant does to persist the entry.
    json.dumps(dict(updated.data), cls=JSONEncoder)


async def test_legacy_entry_without_unique_id_is_adopted(hass):
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
    flow._products = [UserProduct(sn="SN1", name="New Device", stateList=[], online="1")]
    flow._product_client = AsyncMock()

    with patch.object(hass.config_entries, "async_reload", AsyncMock()):
        result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "success"

    updated = hass.config_entries.async_get_entry(legacy_entry.entry_id)
    assert updated.unique_id == ACCOUNT_UNIQUE_ID
    assert updated.options["devices"] == ["SN1"]


async def test_bind_devices_failure_aborts_cannot_connect(hass):
    """Bind devices failure aborts cannot connect."""
    flow = _make_flow(hass)
    flow._product_client = AsyncMock()
    flow._product_client.bind_devices.side_effect = RuntimeError("boom")

    result = await flow.async_step_select_devices(user_input={"devices": ["SN1"]})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_get_user_products_failure_aborts_cannot_connect(hass):
    """Get user products failure aborts cannot connect."""
    flow = _make_flow(hass)

    with patch("homeassistant.components.bluetti.oauth.async_get_clientsession"), \
         patch("homeassistant.components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(side_effect=RuntimeError("boom"))
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_no_devices_available_aborts(hass):
    """No devices available aborts."""
    flow = _make_flow(hass)

    with patch("homeassistant.components.bluetti.oauth.async_get_clientsession"), \
         patch("homeassistant.components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[])
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_all_devices_exists_aborts(hass):
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

    with patch("homeassistant.components.bluetti.oauth.async_get_clientsession"), \
         patch("homeassistant.components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product])
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "all_devices_exists"


async def test_reconfigure_token_updates_existing_entry(hass):
    """When re-running the flow for an existing entry_id, only the token is refreshed."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_UNIQUE_ID,
        title=f"{INTEGRATION_NAME} Power Integration",
        data={"auth_implementation": "bluetti", "token": {"access_token": "old"}, "products": []},
        options={"devices": []},
    )
    existing_entry.add_to_hass(hass)

    flow = _make_flow(hass)
    flow.context = {"entry_id": existing_entry.entry_id}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with patch("homeassistant.components.bluetti.oauth.async_get_clientsession"), \
         patch("homeassistant.components.bluetti.oauth.ProductClient") as mock_client_cls, \
         patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product])
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "success"
    mock_reload.assert_awaited_once_with(existing_entry.entry_id)

    updated = hass.config_entries.async_get_entry(existing_entry.entry_id)
    assert updated.data["token"] == {"access_token": "tok", "expires_at": 9999999999}


async def test_reconfigure_token_missing_entry_aborts(hass):
    """entry_id in context but the entry itself is gone (e.g. removed mid-flow)."""
    flow = _make_flow(hass)
    flow.context = {"entry_id": "does-not-exist"}
    product = UserProduct(sn="SN1", name="Device", stateList=[], online="1")

    with patch("homeassistant.components.bluetti.oauth.async_get_clientsession"), \
         patch("homeassistant.components.bluetti.oauth.ProductClient") as mock_client_cls:
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[product])
        )
        result = await flow.async_step_select_devices(user_input=None)

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_failed"
