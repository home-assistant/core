"""Tests for the BLUETTI options flow (add devices without re-authenticating)."""

from contextlib import asynccontextmanager, contextmanager
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.exceptions import ModbusConnectionError
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


def _temporary_unit_cm(unit=None):
    """Build a stand-in for async_get_temporary_unit's async context manager."""

    @asynccontextmanager
    async def _cm(*_args, **_kwargs):
        yield unit

    return _cm


@contextmanager
def _patched_modbus(device):
    """Patch the options flow's connectivity check to use this fake device."""
    with (
        patch(
            "homeassistant.components.bluetti.options_flow.async_get_temporary_unit",
            _temporary_unit_cm(),
        ),
        patch(
            "homeassistant.components.bluetti.options_flow.get_device",
            return_value=device,
        ) as mock_get_device,
    ):
        yield mock_get_device


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


def _entry(
    hass: HomeAssistant, *, products=None, devices=None, modbus=None
) -> MockConfigEntry:
    options = {"devices": devices or []}
    if modbus is not None:
        options["modbus"] = modbus
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok"},
            "products": products or [],
        },
        options=options,
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
            return_value=SimpleNamespace(data=products)
        )
        result = await flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    # step_id matches the method that actually owns the form
    # (async_step_add_devices), not the router (async_step_init) that
    # delegated to it - this is what lets the real flow manager correctly
    # re-invoke async_step_add_devices on submit instead of re-routing.
    assert result["step_id"] == "add_devices"


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
            return_value=SimpleNamespace(data=[])
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
            return_value=SimpleNamespace(data=products)
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


async def test_init_shows_menu_when_a_modbus_capable_device_is_enabled(
    hass: HomeAssistant,
) -> None:
    """Init shows menu when a modbus capable device is enabled."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)

    result = await flow.async_step_init(user_input=None)

    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert set(result["menu_options"]) == {"add_devices", "configure_modbus"}


async def test_init_falls_through_to_add_devices_when_enabled_device_is_not_modbus_capable(
    hass: HomeAssistant,
) -> None:
    """Init falls through to add devices when enabled device is not modbus capable."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "AC200L",
                "stateList": [],
                "online": "1",
                "model": "AC200L",
            }
        ],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=[])
        )
        result = await flow.async_step_init(user_input=None)

    # AC200L doesn't support Modbus, so no menu is shown and this falls
    # through to the plain add-devices form (which then aborts since there
    # are no more devices to add - the point being tested is "no menu").
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_available"


async def test_configure_modbus_shows_form_with_only_modbus_capable_enabled_devices(
    hass: HomeAssistant,
) -> None:
    """Configure modbus shows form with only modbus capable enabled devices."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            },
            {
                "sn": "SN2",
                "name": "Other",
                "stateList": [],
                "online": "1",
                "model": "AC200L",
            },
        ],
        devices=["SN1", "SN2"],
    )
    flow = _flow(hass, entry)

    result = await flow.async_step_configure_modbus(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "configure_modbus"
    assert list(result["data_schema"].schema["device_sn"].container) == ["SN1"]


def _schema_default(schema, key):
    return next(k for k in schema.schema if k == key).default()


async def test_configure_modbus_prefills_existing_connection_for_the_default_device(
    hass: HomeAssistant,
) -> None:
    """Configure modbus prefills existing connection for the default device."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
        modbus={"SN1": {"host": "10.2.1.60", "port": 1502}},
    )
    flow = _flow(hass, entry)

    result = await flow.async_step_configure_modbus(user_input=None)

    schema = result["data_schema"]
    assert _schema_default(schema, "device_sn") == "SN1"
    assert _schema_default(schema, "host") == "10.2.1.60"
    assert _schema_default(schema, "port") == 1502


async def test_configure_modbus_prefills_blank_when_nothing_saved_yet(
    hass: HomeAssistant,
) -> None:
    """Configure modbus prefills blank when nothing saved yet."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)

    result = await flow.async_step_configure_modbus(user_input=None)

    schema = result["data_schema"]
    assert _schema_default(schema, "host") == ""
    assert _schema_default(schema, "port") == 502


async def test_configure_modbus_preserves_just_typed_values_after_a_failed_attempt(
    hass: HomeAssistant,
) -> None:
    """Configure modbus preserves just typed values after a failed attempt."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    device = MagicMock()
    device.async_update = AsyncMock(
        side_effect=ModbusConnectionError("no route to host")
    )

    with _patched_modbus(device):
        result = await flow.async_step_configure_modbus(
            user_input={"device_sn": "SN1", "host": "10.2.1.99", "port": 1503}
        )

    schema = result["data_schema"]
    assert _schema_default(schema, "host") == "10.2.1.99"
    assert _schema_default(schema, "port") == 1503


async def test_configure_modbus_success_stores_connection_in_options(
    hass: HomeAssistant,
) -> None:
    """Configure modbus success stores connection in options."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    device = MagicMock()
    device.async_update = AsyncMock()

    with _patched_modbus(device) as mock_get_device:
        result = await flow.async_step_configure_modbus(
            user_input={"device_sn": "SN1", "host": "10.2.1.60", "port": 502}
        )

    mock_get_device.assert_called_once_with("balco260", None)
    assert result["type"] == "create_entry"
    # async_create_entry's data REPLACES entry.options wholesale once the
    # real OptionsFlowManager applies it (not exercised by calling the step
    # method directly, see test_configure_modbus_through_real_flow_manager_
    # preserves_devices below) - assert on the returned data itself here.
    assert result["data"]["modbus"] == {"SN1": {"host": "10.2.1.60", "port": 502}}
    assert result["data"]["devices"] == ["SN1"]


async def test_configure_modbus_connection_failure_reshows_form_with_error(
    hass: HomeAssistant,
) -> None:
    """Configure modbus connection failure reshows form with error."""
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
    )
    flow = _flow(hass, entry)
    device = MagicMock()
    device.async_update = AsyncMock(
        side_effect=ModbusConnectionError("no route to host")
    )

    with _patched_modbus(device):
        result = await flow.async_step_configure_modbus(
            user_input={"device_sn": "SN1", "host": "10.2.1.60", "port": 502}
        )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert "modbus" not in updated.options


async def test_configure_modbus_through_real_flow_manager_preserves_devices(
    hass: HomeAssistant,
) -> None:
    """Configure modbus through real flow manager preserves devices."""
    # Regression test for a real bug found via real-hardware testing:
    # OptionsFlowManager.async_finish_flow() applies async_create_entry's
    # data by REPLACING entry.options wholesale - calling the step method
    # directly (as the other tests above do) never exercises that real
    # code path, so it couldn't catch this. Going through the actual flow
    # manager here is the only way to verify entry.options ends up correct.
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
    )
    device = MagicMock()
    device.async_update = AsyncMock()

    with _patched_modbus(device):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "menu"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "configure_modbus"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "configure_modbus"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"device_sn": "SN1", "host": "10.2.1.60", "port": 502}
        )

    assert result["type"] == "create_entry"

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["devices"] == ["SN1"]
    assert updated.options["modbus"] == {"SN1": {"host": "10.2.1.60", "port": 502}}


async def test_add_devices_through_real_flow_manager_preserves_modbus(
    hass: HomeAssistant,
) -> None:
    """Add devices through real flow manager preserves modbus."""
    # Mirror regression test: adding more devices afterwards must not wipe
    # an already-configured Modbus connection for another device.
    entry = _entry(
        hass,
        products=[
            {
                "sn": "SN1",
                "name": "Balco",
                "stateList": [],
                "online": "1",
                "model": "Balco260",
            }
        ],
        devices=["SN1"],
        modbus={"SN1": {"host": "10.2.1.60", "port": 502}},
    )
    products = [UserProduct(sn="SN2", name="New Device", stateList=[], online="1")]

    with (
        _patched_oauth(),
        patch("homeassistant.components.bluetti.options_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.bluetti.options_flow.ProductClient"
        ) as mock_client_cls,
    ):
        mock_client_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=products)
        )
        mock_client_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )

        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == "menu"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_devices"}
        )
        assert result["type"] == "form"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"devices": ["SN2"]}
        )

    assert result["type"] == "create_entry"

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert set(updated.options["devices"]) == {"SN1", "SN2"}
    assert updated.options["modbus"] == {"SN1": {"host": "10.2.1.60", "port": 502}}


async def test_add_devices_through_real_flow_manager_reloads_exactly_once(
    hass: HomeAssistant,
) -> None:
    """Adding devices through the real options flow must reload the entry once.

    Regression test: async_step_add_devices used to call async_update_entry()
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
            return_value=SimpleNamespace(data=products)
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
