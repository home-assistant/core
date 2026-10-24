"""LAN setup, transport selection and shared listener regression coverage."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from besen.client import BesenClient
from besen.exceptions import CannotConnect, InvalidAuth
from besen.udp import BesenUdpClient
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.besen.config_flow import BesenConfigFlow
from homeassistant.components.besen.const import CONF_SERIAL, CONF_TRANSPORT, DOMAIN
from homeassistant.components.besen.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.besen.lan import (
    async_acquire_udp_hub,
    async_release_udp_hub,
)
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    SOURCE_BLUETOOTH,
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import publish_besen_state
from .conftest import (
    FAKE_SERVICE_INFO,
    FIXTURE_ADDRESS,
    FIXTURE_PIN,
    _configure_client_mock,
    charger_state,
)

SERIAL = "8949281891483449"
HOST = "192.0.2.10"


@pytest.fixture(autouse=True)
def hub() -> Generator[Mock]:
    """Keep setup tests independent of the host's network."""
    hub = Mock(async_start=AsyncMock(), async_stop=AsyncMock())
    with patch("homeassistant.components.besen.lan.BesenUdpHub", return_value=hub):
        yield hub


@pytest.fixture
def udp_client() -> Generator[Mock]:
    """Prepare udp client."""

    client = Mock(spec=BesenUdpClient)
    _configure_client_mock(client)
    client.state = charger_state().updated(
        info=charger_state().info.updated(serial=SERIAL)
    )
    client.is_connected = False
    client.host = HOST
    client.async_wait_for_status = AsyncMock()
    client.async_wait_for_heartbeat = AsyncMock()
    with (
        patch("homeassistant.components.besen.BesenUdpClient", return_value=client),
        patch(
            "homeassistant.components.besen.config_flow.BesenUdpClient",
            return_value=client,
        ),
    ):
        yield client


def flow_for(
    hass: HomeAssistant, entry: MockConfigEntry | None = None
) -> BesenConfigFlow:
    """Prepare flow for."""

    flow = BesenConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}
    if entry:
        entry.add_to_hass(hass)
        flow.context = {"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id}
        flow._pending_data = dict(entry.data)
        flow._pending_data[CONF_SERIAL] = SERIAL
    return flow


async def test_reconfigure_offers_only_connection_selection(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that reconfigure offers only connection selection."""

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["lan", "use_bluetooth"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "lan"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "lan"


async def test_lan_switch_preserves_entry_and_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that lan switch preserves entry and entities."""

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = entity_registry
    before = {
        entry.entity_id: (entry.unique_id, entry.device_id)
        for entry in er.async_entries_for_config_entry(
            registry, mock_config_entry.entry_id
        )
    }
    flow = BesenConfigFlow()
    flow.hass = hass
    flow.context = {
        "source": SOURCE_RECONFIGURE,
        "entry_id": mock_config_entry.entry_id,
    }
    await flow.async_step_reconfigure()
    result = await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await flow._operation_task
    udp_client.async_wait_for_status.assert_awaited_once_with(timeout=10)
    udp_client.async_wait_for_heartbeat.assert_awaited_once()
    assert (await flow.async_step_connect())[
        "type"
    ] is FlowResultType.SHOW_PROGRESS_DONE
    result = await flow.async_step_connection_done()
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == FIXTURE_ADDRESS
    assert mock_config_entry.data[CONF_ADDRESS] == FIXTURE_ADDRESS
    assert mock_config_entry.data[CONF_TRANSPORT] == "lan"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert before == {
        entry.entity_id: (entry.unique_id, entry.device_id)
        for entry in er.async_entries_for_config_entry(
            registry, mock_config_entry.entry_id
        )
    }


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(CannotConnect("offline"), "cannot_connect", id="offline"),
        pytest.param(InvalidAuth("rejected"), "invalid_auth", id="invalid-auth"),
        pytest.param(TimeoutError(), "cannot_connect", id="timeout"),
        pytest.param(RuntimeError("private-pin"), "unknown", id="unexpected-error"),
    ],
)
async def test_failed_lan_validation_restores_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
    error: Exception,
    expected: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that failed lan validation restores connection."""

    mock_besen_client.is_connected = False
    flow = flow_for(hass, mock_config_entry)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.reset_mock()
    original = dict(mock_config_entry.data)
    udp_client.async_start.side_effect = error
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    result = await flow.async_step_connection_done()
    assert result["errors"] == {"base": expected}
    assert mock_config_entry.data == original
    mock_besen_client.async_start.assert_awaited_once()
    udp_client.async_stop.assert_awaited_once()
    assert "private-pin" not in caplog.text


async def test_cancel_reconfigure_restores_original_transport(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
) -> None:
    """Test that cancel reconfigure restores original transport."""

    mock_besen_client.is_connected = False
    flow = flow_for(hass, mock_config_entry)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.reset_mock()
    started = asyncio.Event()

    async def connect() -> None:
        """Prepare connect."""

        started.set()
        await asyncio.Event().wait()

    udp_client.async_start.side_effect = connect
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await started.wait()
    flow.async_remove()
    with pytest.raises(asyncio.CancelledError):
        await flow._operation_task
    mock_besen_client.async_start.assert_awaited_once()
    udp_client.async_stop.assert_awaited_once()
    assert CONF_TRANSPORT not in mock_config_entry.data


@pytest.mark.parametrize(
    "pin",
    [
        pytest.param("12345", id="too-short"),
        pytest.param("\uff11\uff12\uff13\uff14\uff15\uff16", id="non-ascii"),
    ],
)
async def test_invalid_lan_pin_never_connects(
    hass: HomeAssistant, udp_client: Mock, pin: str
) -> None:
    """Test that invalid lan pin never connects."""

    flow = flow_for(hass)
    result = await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: pin})
    assert result["errors"] == {"base": "invalid_auth"}
    udp_client.async_start.assert_not_awaited()


async def test_empty_lan_host_never_connects(
    hass: HomeAssistant, udp_client: Mock
) -> None:
    """Test that empty lan host never connects."""

    flow = flow_for(hass)
    result = await flow.async_step_lan({CONF_HOST: "  ", CONF_PIN: FIXTURE_PIN})
    assert result["errors"] == {"base": "cannot_connect"}
    udp_client.async_start.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry", "udp_client")
async def test_new_lan_entry_uses_serial_identity(hass: HomeAssistant) -> None:
    """Test that new lan entry uses serial identity."""

    flow = flow_for(hass)
    await flow.async_step_user({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    result = await flow.async_step_connection_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert flow.unique_id == f"lan:{SERIAL}"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PIN: FIXTURE_PIN,
        CONF_SERIAL: SERIAL,
        CONF_ADDRESS: f"lan:{SERIAL}",
        CONF_NAME: "BS20",
        CONF_TRANSPORT: "lan",
    }


@pytest.mark.usefixtures("udp_client")
async def test_duplicate_lan_serial_is_rejected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that duplicate lan serial is rejected."""

    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, SERIAL)}
    )
    flow = flow_for(hass)
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    result = await flow.async_step_connection_done()
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_no_identity_cannot_be_saved(
    hass: HomeAssistant, udp_client: Mock
) -> None:
    """Test that no identity cannot be saved."""

    udp_client.state = udp_client.state.updated(
        info=udp_client.state.info.updated(serial=None)
    )
    flow = flow_for(hass)
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    assert (await flow.async_step_connection_done())["errors"] == {
        "base": "cannot_connect"
    }


async def test_lan_only_entry_does_not_offer_unknown_bluetooth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that lan only entry does not offer unknown bluetooth."""

    flow = flow_for(hass, mock_config_entry)
    flow._pending_data[CONF_ADDRESS] = f"lan:{SERIAL}"
    assert (await flow.async_step_use_bluetooth())[
        "reason"
    ] == "bluetooth_address_unknown"


async def test_bluetooth_switch_validates_before_saving(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test that bluetooth switch validates before saving."""

    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    flow = flow_for(hass, mock_config_entry)
    assert (await flow.async_step_use_bluetooth())["type"] is FlowResultType.FORM
    await flow.async_step_use_bluetooth({CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()):
        result = await flow.async_step_connection_done()
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TRANSPORT] == "bluetooth"


@pytest.mark.usefixtures("udp_client")
async def test_lan_reauth_updates_only_after_verification(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that lan reauth updates only after verification."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    flow = BesenConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id}
    await flow.async_step_reauth_confirm({CONF_PIN: "654321"})
    await flow._operation_task
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()):
        result = await flow.async_step_connection_done()
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PIN] == "654321"


async def test_listener_shared_until_final_user_releases(
    hass: HomeAssistant, hub: Mock
) -> None:
    """Test that listener shared until final user releases."""

    first, second = await asyncio.gather(
        async_acquire_udp_hub(hass), async_acquire_udp_hub(hass)
    )
    assert first is second is hub
    await async_release_udp_hub(hass)
    hub.async_stop.assert_not_awaited()
    await async_release_udp_hub(hass)
    hub.async_stop.assert_awaited_once()


async def test_runtime_lan_ignores_missing_bluetooth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    mock_ble_device: Mock,
    mock_besen_client: Mock,
    hub: Mock,
) -> None:
    """Test that runtime lan ignores missing bluetooth."""

    mock_ble_device.return_value = None
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.assert_not_awaited()
    assert hass.states.get("switch.garage_charge").state == "on"
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    hub.async_stop.assert_awaited_once()


async def test_listener_bind_error_retries_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    hub: Mock,
) -> None:
    """Test that listener bind error retries entry."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    hub.async_start.side_effect = CannotConnect("bind failed")
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    udp_client.async_start.assert_not_awaited()


async def test_runtime_failed_login_releases_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    hub: Mock,
) -> None:
    """Test that runtime failed login releases listener."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    udp_client.async_start.side_effect = InvalidAuth("rejected")
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    hub.async_stop.assert_awaited_once()


@pytest.mark.parametrize(
    "saved_serial",
    [
        pytest.param({}, id="missing"),
        pytest.param({CONF_SERIAL: None}, id="null"),
        pytest.param({CONF_SERIAL: ""}, id="empty"),
    ],
)
async def test_reconfigure_recovers_identity_from_unloaded_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    saved_serial: dict[str, str | None],
) -> None:
    """Test that reconfigure recovers identity from unloaded device."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, **saved_serial}
    )
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, FIXTURE_ADDRESS)},
        serial_number=SERIAL,
    )
    flow = BesenConfigFlow()
    flow.hass = hass
    flow.context = {
        "source": SOURCE_RECONFIGURE,
        "entry_id": mock_config_entry.entry_id,
    }
    await flow.async_step_reconfigure()
    assert flow._pending_data[CONF_SERIAL] == SERIAL


async def test_reconfigure_rejects_unknown_identity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, udp_client: Mock
) -> None:
    """Test that reconfigure rejects unknown identity."""

    flow = flow_for(hass, mock_config_entry)
    del flow._pending_data[CONF_SERIAL]
    result = await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    assert result["errors"] == {"base": "identity_unknown"}
    udp_client.async_start.assert_not_awaited()


async def test_reconfigure_rejects_different_charger(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, udp_client: Mock
) -> None:
    """Test that reconfigure rejects different charger."""

    flow = flow_for(hass, mock_config_entry)
    udp_client.state = udp_client.state.updated(
        info=udp_client.state.info.updated(serial="1122334455667788")
    )
    original = dict(mock_config_entry.data)
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    assert (await flow.async_step_connection_done())["errors"] == {
        "base": "wrong_device"
    }
    assert mock_config_entry.data == original


async def test_old_connection_must_release_before_lan(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
) -> None:
    """Test that old connection must release before lan."""

    mock_besen_client.is_connected = True
    flow = flow_for(hass, mock_config_entry)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.reset_mock()
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    assert (await flow.async_step_connection_done())["errors"] == {
        "base": "cannot_connect"
    }
    udp_client.async_start.assert_not_awaited()


@pytest.mark.usefixtures("udp_client")
async def test_failed_restoration_requests_saved_entry_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Test that failed restoration requests saved entry reload."""

    mock_besen_client.is_connected = False
    flow = flow_for(hass, mock_config_entry)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.reset_mock()
    mock_besen_client.async_start.side_effect = CannotConnect("restore failed")
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
        await flow._operation_task
        await hass.async_block_till_done()
        reload.assert_not_awaited()
        flow.async_remove()
        await hass.async_block_till_done()
    reload.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_failed_lan_reauth_keeps_pin(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, udp_client: Mock
) -> None:
    """Test that failed lan reauth keeps pin."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    flow = BesenConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id}
    udp_client.async_start.side_effect = InvalidAuth("rejected")
    await flow.async_step_reauth_confirm({CONF_PIN: "654321"})
    await flow._operation_task
    result = await flow.async_step_connection_done()
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN


async def test_invalid_lan_reauth_pin_never_connects(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, udp_client: Mock
) -> None:
    """Test that invalid lan reauth pin never connects."""

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_TRANSPORT: "lan"}
    )
    flow = BesenConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id}
    result = await flow.async_step_reauth_confirm({CONF_PIN: "12345"})
    assert result["errors"] == {"base": "invalid_auth"}
    udp_client.async_start.assert_not_awaited()


async def test_user_must_choose_a_connection(hass: HomeAssistant) -> None:
    """Test that user must choose a connection."""

    flow = flow_for(hass)
    result = await flow.async_step_user({CONF_PIN: FIXTURE_PIN})
    assert result["errors"] == {"base": "choose_connection"}


async def test_second_reconfigure_is_blocked(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that second reconfigure is blocked."""

    mock_config_entry.add_to_hass(hass)
    first = await mock_config_entry.start_reconfigure_flow(hass)
    assert first["type"] is FlowResultType.MENU
    second = await mock_config_entry.start_reconfigure_flow(hass)
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"


async def test_lan_only_identity_updates_controls_and_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    mock_besen_client: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that lan only identity updates controls and diagnostics."""

    address = f"lan:{SERIAL}"
    udp_client.address = address
    udp_client.state = udp_client.state.updated(
        info=udp_client.state.info.updated(address=address)
    )
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        unique_id=address,
        data={
            **mock_config_entry.data,
            CONF_ADDRESS: address,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    (device,) = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device.connections == set()
    assert device.identifiers == {(DOMAIN, SERIAL)}
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.garage_charging_current", "value": 6},
        blocking=True,
    )
    udp_client.async_set_charge_amps.assert_awaited_once_with(6)
    mock_besen_client.async_set_charge_amps.assert_not_awaited()
    publish_besen_state(
        udp_client,
        udp_client.state.updated(config=udp_client.state.config.updated(charge_amps=6)),
    )
    await hass.async_block_till_done()
    assert hass.states.get("number.garage_charging_current").state == "6"
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diagnostics["entry_data"][CONF_HOST] == "**REDACTED**"
    assert HOST not in repr(diagnostics)
    assert FIXTURE_PIN not in repr(diagnostics)


@pytest.mark.parametrize(
    ("source", "discovery", "user_input"),
    [
        pytest.param(
            SOURCE_BLUETOOTH,
            FAKE_SERVICE_INFO,
            {CONF_PIN: FIXTURE_PIN},
            id="bluetooth-discovery",
        ),
        pytest.param(
            SOURCE_USER,
            None,
            {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
            id="manual-bluetooth",
        ),
    ],
)
async def test_bluetooth_rejects_charger_already_added_over_lan(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    source: str,
    discovery: BluetoothServiceInfoBleak | None,
    user_input: dict[str, str],
) -> None:
    """Reject a Bluetooth duplicate of an existing LAN charger by serial."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        unique_id=f"lan:{SERIAL}",
        data={
            **mock_config_entry.data,
            CONF_ADDRESS: f"lan:{SERIAL}",
            CONF_SERIAL: SERIAL,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
        },
    )
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("udp_client")
async def test_duplicate_added_before_lan_validation_is_saved(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Recheck serial identity when another flow adds the charger first."""
    flow = flow_for(hass)
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SERIAL: SERIAL},
    )
    result = await flow.async_step_connection_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("udp_client", "mock_setup_entry")
async def test_lan_setup_flow_checks_connection_before_creating_entry(
    hass: HomeAssistant,
) -> None:
    """Exercise the complete LAN setup flow through Home Assistant."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == f"lan:{SERIAL}"
    assert result["data"][CONF_TRANSPORT] == "lan"


async def test_bluetooth_reconfigure_rejects_another_configured_charger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Reject a Bluetooth target whose serial belongs to another entry."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"lan:{SERIAL}",
        data={
            CONF_ADDRESS: f"lan:{SERIAL}",
            CONF_SERIAL: SERIAL,
            CONF_HOST: HOST,
            CONF_PIN: FIXTURE_PIN,
            CONF_TRANSPORT: "lan",
        },
    )
    other_entry.add_to_hass(hass)
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    flow = flow_for(hass, mock_config_entry)
    original = dict(mock_config_entry.data)
    await flow.async_step_use_bluetooth({CONF_PIN: FIXTURE_PIN})
    await flow._operation_task
    result = await flow.async_step_connection_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == original


@pytest.mark.parametrize(
    ("source", "discovery", "user_input"),
    [
        pytest.param(
            SOURCE_BLUETOOTH, FAKE_SERVICE_INFO, {CONF_PIN: FIXTURE_PIN}, id="discovery"
        ),
        pytest.param(
            SOURCE_USER,
            None,
            {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
            id="manual",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_serial_checked_after_validation_client_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    source: str,
    discovery: BluetoothServiceInfoBleak | None,
    user_input: dict[str, str],
) -> None:
    """Reject a LAN duplicate added while Bluetooth cleanup is suspended."""
    stopping = asyncio.Event()
    finish_stop = asyncio.Event()

    async def stop() -> None:
        """Wait until another flow has saved the charger."""
        stopping.set()
        await finish_stop.wait()

    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    mock_besen_client.async_stop.side_effect = stop
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery
    )
    validation = hass.async_create_task(
        hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    )
    await stopping.wait()
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        unique_id=f"lan:{SERIAL}",
        data={
            **mock_config_entry.data,
            CONF_ADDRESS: f"lan:{SERIAL}",
            CONF_SERIAL: SERIAL,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
        },
    )
    finish_stop.set()
    result = await validation
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_validation_does_not_restart_an_unloaded_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
) -> None:
    """Do not resurrect a captured client after its entry has unloaded."""
    validating = asyncio.Event()
    finish_validation = asyncio.Event()
    shutdown_started = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Hold the candidate until the old coordinator has shut down."""
        validating.set()
        await finish_validation.wait()

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    flow = flow_for(hass, mock_config_entry)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    udp_client.async_wait_for_status.side_effect = wait_for_status
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await validating.wait()
    mock_besen_client.add_listener.return_value.side_effect = shutdown_started.set
    unloading = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await shutdown_started.wait()
    finish_validation.set()
    await flow._operation_task
    assert await unloading
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_besen_client.async_start.assert_awaited_once()
    mock_besen_client.add_listener.return_value.assert_called_once_with()


async def test_shutdown_waits_for_connection_restoration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
) -> None:
    """Finish an in-flight restart before shutdown performs its final stop."""
    restoring = asyncio.Event()
    finish_restore = asyncio.Event()
    shutdown_started = asyncio.Event()
    events: list[str] = []

    async def restore() -> None:
        """Hold the original client's restart until teardown begins."""
        restoring.set()
        await finish_restore.wait()
        events.append("restored")

    async def stop() -> None:
        """Record the stop order relative to the blocked restart."""
        events.append("stopped")

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    flow = flow_for(hass, mock_config_entry)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.side_effect = restore
    mock_besen_client.async_stop.side_effect = stop
    mock_besen_client.add_listener.return_value.side_effect = shutdown_started.set
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await restoring.wait()
    unloading = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await shutdown_started.wait()
    finish_restore.set()
    await flow._operation_task
    assert await unloading
    assert events == ["stopped", "restored", "stopped"]
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "restore_error",
    [
        pytest.param(InvalidAuth("old PIN rejected"), id="invalid-auth"),
        pytest.param(CannotConnect("restore failed"), id="cannot-connect"),
    ],
)
async def test_loaded_lan_reauth_survives_old_connection_restore_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    restore_error: Exception,
) -> None:
    """Save a verified new PIN before any reload can abort reauthentication."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    current = udp_client
    candidate = Mock(spec=BesenUdpClient)
    _configure_client_mock(candidate)
    candidate.state = current.state
    candidate.host = HOST
    candidate.is_connected = False
    current.async_start.side_effect = restore_error
    with (
        patch(
            "homeassistant.components.besen.config_flow.BesenUdpClient",
            return_value=candidate,
        ),
        patch("homeassistant.components.besen.BesenUdpClient", return_value=candidate),
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "654321"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()
        assert [
            flow["flow_id"] for flow in hass.config_entries.flow.async_progress()
        ] == [result["flow_id"]]
        assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
    assert mock_config_entry.data[CONF_PIN] == "654321"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is candidate


async def test_pin_rejection_can_start_reauth_after_reconfigure_is_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Allow reauthentication after a reconfiguration suppressed an earlier request."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    reconfigure = await mock_config_entry.start_reconfigure_flow(hass)
    rejected = charger_state(available=False, authenticated=False).updated(
        auth_failed=True
    )
    publish_besen_state(mock_besen_client, rejected)
    await hass.async_block_till_done()
    assert list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})) == []
    hass.config_entries.flow.async_abort(reconfigure["flow_id"])
    publish_besen_state(mock_besen_client, rejected)
    await hass.async_block_till_done()
    assert (
        len(list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))) == 1
    )
    publish_besen_state(mock_besen_client, rejected)
    await hass.async_block_till_done()
    assert (
        len(list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))) == 1
    )


async def test_shutdown_coordinator_refuses_new_connection_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Reject a pause request queued after its coordinator has been unloaded."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    with pytest.raises(CannotConnect, match="unloading"):
        await coordinator.async_pause_connection()
    mock_besen_client.async_start.assert_awaited_once()


async def test_cancelled_reauth_reloads_only_after_restoration_finishes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
) -> None:
    """Complete cancellation cleanup before retrying the saved connection."""
    validating = asyncio.Event()
    reloaded = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Wait for cancellation while the candidate owns the connection."""
        validating.set()
        await asyncio.Event().wait()

    async def reload_entry(entry_id: str) -> bool:
        """Check that a recovery reload cannot abort its own active flow."""
        assert entry_id == mock_config_entry.entry_id
        assert (
            list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})) == []
        )
        assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
        reloaded.set()
        return True

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    candidate = Mock(spec=BesenUdpClient)
    _configure_client_mock(candidate)
    candidate.state = udp_client.state
    candidate.host = HOST
    candidate.async_wait_for_status.side_effect = wait_for_status
    udp_client.async_start.side_effect = InvalidAuth("old PIN rejected")
    with (
        patch(
            "homeassistant.components.besen.config_flow.BesenUdpClient",
            return_value=candidate,
        ),
        patch.object(
            hass.config_entries, "async_reload", side_effect=reload_entry
        ) as reload,
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "654321"}
        )
        await validating.wait()
        reload.assert_not_awaited()
        hass.config_entries.flow.async_abort(result["flow_id"])
        await reloaded.wait()
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(mock_config_entry.entry_id)
    candidate.async_stop.assert_awaited_once()
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN


async def test_deferred_recovery_does_not_reload_an_unloaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
) -> None:
    """Discard a deferred retry when the user unloads the entry first."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    candidate = Mock(spec=BesenUdpClient)
    _configure_client_mock(candidate)
    candidate.state = udp_client.state
    candidate.host = HOST
    udp_client.async_start.side_effect = InvalidAuth("old PIN rejected")
    with (
        patch(
            "homeassistant.components.besen.config_flow.BesenUdpClient",
            return_value=candidate,
        ),
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload,
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "654321"}
        )
        await hass.async_block_till_done()
        reload.assert_not_awaited()
        hass.config_entries.flow.async_abort(result["flow_id"])
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        reload.assert_not_awaited()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("source", "discovery", "user_input"),
    [
        pytest.param(
            SOURCE_BLUETOOTH, FAKE_SERVICE_INFO, {CONF_PIN: FIXTURE_PIN}, id="discovery"
        ),
        pytest.param(
            SOURCE_USER,
            None,
            {CONF_ADDRESS: FIXTURE_ADDRESS, CONF_PIN: FIXTURE_PIN},
            id="manual",
        ),
    ],
)
@pytest.mark.usefixtures("udp_client")
async def test_failed_bluetooth_setup_still_blocks_lan_duplicate(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_besen_client: Mock,
    source: str,
    discovery: BluetoothServiceInfoBleak | None,
    user_input: dict[str, str],
) -> None:
    """Retain serial identity when entry setup fails before creating devices."""
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    mock_besen_client.async_start.side_effect = [None, CannotConnect("setup failed")]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hasattr(entry, "runtime_data")
    assert dr.async_entries_for_config_entry(device_registry, entry.entry_id) == []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert entry.data[CONF_SERIAL] == SERIAL


async def test_cancel_during_restoration_reloads_saved_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
    hub: Mock,
) -> None:
    """Recover the saved transport when flow removal interrupts its restart."""
    restoring = asyncio.Event()

    async def restore() -> None:
        """Hold restoration until the user cancels the flow."""
        restoring.set()
        await asyncio.Event().wait()

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_besen_client.async_start.side_effect = restore
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "lan"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
        )
        await restoring.wait()
        flow = hass.config_entries.flow._progress[result["flow_id"]]
        assert isinstance(flow, BesenConfigFlow)
        assert flow._operation_task is not None
        operation = flow._operation_task
        mock_besen_client.async_start.side_effect = None
        reload.assert_not_awaited()
        hass.config_entries.flow.async_abort(result["flow_id"])
        with pytest.raises(asyncio.CancelledError):
            await operation
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
    assert CONF_TRANSPORT not in mock_config_entry.data
    assert (
        list(mock_config_entry.async_get_active_flows(hass, {SOURCE_RECONFIGURE})) == []
    )
    assert mock_besen_client.async_start.await_count == 3
    udp_client.async_stop.assert_awaited_once()
    hub.async_stop.assert_awaited_once()


@pytest.fixture
def validation_clients(udp_client: Mock) -> Generator[tuple[Mock, Mock]]:
    """Give overlapping flows separate candidates for the same charger."""
    first = Mock(spec=BesenUdpClient)
    second = Mock(spec=BesenUdpClient)
    for client in (first, second):
        _configure_client_mock(client)
        client.state = udp_client.state
        client.host = HOST
        client.is_connected = False
        client.async_wait_for_status = AsyncMock()
        client.async_wait_for_heartbeat = AsyncMock()
    with patch(
        "homeassistant.components.besen.config_flow.BesenUdpClient",
        side_effect=(first, second),
    ):
        yield first, second


async def test_cancelled_validation_finishes_before_replacement_starts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
    validation_clients: tuple[Mock, Mock],
) -> None:
    """Keep ownership after cancellation until cleanup and restoration finish."""
    first, second = validation_clients
    validating = asyncio.Event()
    cleaning = asyncio.Event()
    finish_cleanup = asyncio.Event()
    restoring = asyncio.Event()
    finish_restore = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Keep the first flow active until its dialog is cancelled."""
        validating.set()
        await asyncio.Event().wait()

    async def stop_candidate() -> None:
        """Hold candidate cleanup after the flow is removed from the manager."""
        cleaning.set()
        await finish_cleanup.wait()

    async def restore() -> None:
        """Hold restoration after candidate cleanup has finished."""
        restoring.set()
        await finish_restore.wait()

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    first.async_wait_for_status.side_effect = wait_for_status
    first.async_stop.side_effect = stop_candidate
    mock_besen_client.async_start.side_effect = restore
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "lan"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    first_flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert isinstance(first_flow, BesenConfigFlow)
    await validating.wait()
    hass.config_entries.flow.async_abort(result["flow_id"])
    await cleaning.wait()
    replacement = await mock_config_entry.start_reconfigure_flow(hass)
    replacement = await hass.config_entries.flow.async_configure(
        replacement["flow_id"], {"next_step_id": "lan"}
    )
    replacement = await hass.config_entries.flow.async_configure(
        replacement["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    replacement_flow = hass.config_entries.flow._progress[replacement["flow_id"]]
    assert isinstance(replacement_flow, BesenConfigFlow)
    try:
        await asyncio.sleep(0)
        second.async_start.assert_not_awaited()
        finish_cleanup.set()
        await restoring.wait()
        second.async_start.assert_not_awaited()
    finally:
        mock_besen_client.async_start.side_effect = None
        finish_cleanup.set()
        finish_restore.set()
        assert first_flow._operation_task is not None
        assert replacement_flow._operation_task is not None
        await asyncio.gather(
            first_flow._operation_task,
            replacement_flow._operation_task,
            return_exceptions=True,
        )
        hass.config_entries.flow.async_abort(replacement["flow_id"])
    assert first_flow._operation_task.cancelled()
    first.async_stop.assert_awaited_once()
    second.async_start.assert_awaited_once()
    second.async_stop.assert_awaited_once()
    assert mock_besen_client.async_start.await_count == 3
    assert CONF_TRANSPORT not in mock_config_entry.data


@pytest.mark.parametrize(
    ("first_source", "second_source"),
    [
        pytest.param(SOURCE_REAUTH, SOURCE_RECONFIGURE, id="reauth-first"),
        pytest.param(SOURCE_RECONFIGURE, SOURCE_REAUTH, id="reconfigure-first"),
    ],
)
async def test_reauth_and_reconfigure_serialize_entire_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    validation_clients: tuple[Mock, Mock],
    first_source: str,
    second_source: str,
) -> None:
    """Serialize candidates and restoration in either submission order."""
    first, second = validation_clients
    validating = asyncio.Event()
    finish_validation = asyncio.Event()
    restoring = asyncio.Event()
    finish_restore = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Hold validation while the other flow is submitted."""
        validating.set()
        await finish_validation.wait()

    async def restore() -> None:
        """Hold restoration after candidate validation succeeds."""
        restoring.set()
        await finish_restore.wait()

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    reauth = await mock_config_entry.start_reauth_flow(hass)
    reconfigure = await mock_config_entry.start_reconfigure_flow(hass)
    reconfigure = await hass.config_entries.flow.async_configure(
        reconfigure["flow_id"], {"next_step_id": "lan"}
    )
    forms = {SOURCE_REAUTH: reauth, SOURCE_RECONFIGURE: reconfigure}
    inputs = {
        SOURCE_REAUTH: {CONF_PIN: "654321"},
        SOURCE_RECONFIGURE: {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN},
    }
    first.async_wait_for_status.side_effect = wait_for_status
    udp_client.async_start.side_effect = restore
    await hass.config_entries.flow.async_configure(
        forms[first_source]["flow_id"], inputs[first_source]
    )
    await validating.wait()
    await hass.config_entries.flow.async_configure(
        forms[second_source]["flow_id"], inputs[second_source]
    )
    first_flow = hass.config_entries.flow._progress[forms[first_source]["flow_id"]]
    second_flow = hass.config_entries.flow._progress[forms[second_source]["flow_id"]]
    assert isinstance(first_flow, BesenConfigFlow)
    assert isinstance(second_flow, BesenConfigFlow)
    try:
        await asyncio.sleep(0)
        second.async_start.assert_not_awaited()
        finish_validation.set()
        await restoring.wait()
        second.async_start.assert_not_awaited()
    finally:
        udp_client.async_start.side_effect = None
        finish_validation.set()
        finish_restore.set()
        assert first_flow._operation_task is not None
        assert second_flow._operation_task is not None
        await asyncio.gather(first_flow._operation_task, second_flow._operation_task)
        hass.config_entries.flow.async_abort(forms[first_source]["flow_id"])
        hass.config_entries.flow.async_abort(forms[second_source]["flow_id"])
    first.async_stop.assert_awaited_once()
    second.async_start.assert_awaited_once()
    second.async_stop.assert_awaited_once()
    assert udp_client.async_start.await_count == 3
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN


async def test_validation_waits_for_entry_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
) -> None:
    """Pause the newly loaded coordinator before opening a validation client."""
    starting = asyncio.Event()
    finish_startup = asyncio.Event()

    async def start() -> None:
        """Hold startup before the runtime coordinator is assigned to its entry."""
        starting.set()
        await finish_startup.wait()

    async def start_candidate() -> None:
        """Require release of the runtime discovered after waiting for ownership."""
        mock_besen_client.async_stop.assert_awaited_once()

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    mock_besen_client.async_start.side_effect = start
    udp_client.async_start.side_effect = start_candidate
    flow = flow_for(hass, mock_config_entry)
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    await starting.wait()
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    try:
        await asyncio.sleep(0)
        udp_client.async_start.assert_not_awaited()
    finally:
        mock_besen_client.async_start.side_effect = None
        finish_startup.set()
    assert await setup
    await flow._operation_task
    udp_client.async_start.assert_awaited_once()
    udp_client.async_stop.assert_awaited_once()
    assert mock_besen_client.async_start.await_count == 2
    flow.async_remove()


async def test_entry_startup_waits_for_validation_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
) -> None:
    """Keep a new runtime from opening while an unloaded entry is validated."""
    validating = asyncio.Event()
    finish_validation = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Hold the candidate while entry setup starts."""
        validating.set()
        await finish_validation.wait()

    async def start() -> None:
        """Require candidate cleanup before the saved client can start."""
        udp_client.async_stop.assert_awaited_once()

    mock_besen_client.state = udp_client.state
    mock_besen_client.async_start.side_effect = start
    udp_client.async_wait_for_status.side_effect = wait_for_status
    flow = flow_for(hass, mock_config_entry)
    await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
    await validating.wait()
    setup = hass.async_create_task(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    try:
        await asyncio.sleep(0)
        mock_besen_client.async_start.assert_not_awaited()
    finally:
        finish_validation.set()
    await flow._operation_task
    assert await setup
    mock_besen_client.async_start.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flow.async_remove()


async def test_loaded_bluetooth_reauth_uses_the_validation_transaction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
) -> None:
    """Release the saved Bluetooth session before testing a replacement PIN."""
    candidate = Mock(spec=BesenClient)
    _configure_client_mock(candidate)

    async def validate() -> None:
        """Require the old session to be stopped before Bluetooth validation."""
        mock_besen_client.async_stop.assert_awaited_once()

    candidate.async_start.side_effect = validate
    mock_besen_client.is_connected = False
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.besen.config_flow.BesenClient", return_value=candidate
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "654321"}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()
        assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()
    assert mock_config_entry.data[CONF_PIN] == "654321"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    candidate.async_start.assert_awaited_once()
    candidate.async_stop.assert_awaited_once()


async def test_cancelling_queued_validation_preserves_current_owner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    validation_clients: tuple[Mock, Mock],
) -> None:
    """Cancelling a waiter cannot release another flow's connection ownership."""
    first, second = validation_clients
    validating = asyncio.Event()
    finish_validation = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Hold the owner while its waiting flow is cancelled."""
        validating.set()
        await finish_validation.wait()

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    reauth = await mock_config_entry.start_reauth_flow(hass)
    reconfigure = await mock_config_entry.start_reconfigure_flow(hass)
    reconfigure = await hass.config_entries.flow.async_configure(
        reconfigure["flow_id"], {"next_step_id": "lan"}
    )
    first.async_wait_for_status.side_effect = wait_for_status
    await hass.config_entries.flow.async_configure(
        reauth["flow_id"], {CONF_PIN: "654321"}
    )
    await validating.wait()
    await hass.config_entries.flow.async_configure(
        reconfigure["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    owner = hass.config_entries.flow._progress[reauth["flow_id"]]
    waiter = hass.config_entries.flow._progress[reconfigure["flow_id"]]
    assert isinstance(owner, BesenConfigFlow)
    assert isinstance(waiter, BesenConfigFlow)
    try:
        await asyncio.sleep(0)
        hass.config_entries.flow.async_abort(reconfigure["flow_id"])
        with pytest.raises(asyncio.CancelledError):
            await waiter._operation_task
        second.async_start.assert_not_awaited()
        first.async_stop.assert_not_awaited()
        udp_client.async_start.assert_awaited_once()
    finally:
        finish_validation.set()
        await owner._operation_task
        hass.config_entries.flow.async_abort(reauth["flow_id"])
    first.async_stop.assert_awaited_once()
    assert udp_client.async_start.await_count == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_failed_candidate_cleanup_does_not_save_connection(
    hass: HomeAssistant, udp_client: Mock
) -> None:
    """Keep the form open when a verified candidate cannot be shut down."""
    udp_client.async_stop.side_effect = CannotConnect("cleanup failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "lan"
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []
    udp_client.async_stop.side_effect = None
    hass.config_entries.flow.async_abort(result["flow_id"])


@pytest.mark.parametrize(
    "cleanup_failure",
    [
        pytest.param(None, id="success"),
        pytest.param(CannotConnect("stop failed"), id="failure"),
    ],
)
async def test_cancellation_waits_for_candidate_shutdown_with_shared_hub(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
    hub: Mock,
    cleanup_failure: Exception | None,
) -> None:
    """Complete candidate shutdown before restoring while another hub user exists."""
    stopping = asyncio.Event()
    finish_stop = asyncio.Event()
    stopped = asyncio.Event()
    stop_cancelled = asyncio.Event()

    async def stop() -> None:
        """Keep shutdown pending while the flow is cancelled twice."""
        stopping.set()
        try:
            await finish_stop.wait()
        except asyncio.CancelledError:
            stop_cancelled.set()
            raise
        stopped.set()
        Mock(side_effect=cleanup_failure)()

    mock_besen_client.is_connected = False
    mock_besen_client.state = udp_client.state
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_acquire_udp_hub(hass)
    udp_client.async_stop.side_effect = stop
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "lan"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert isinstance(flow, BesenConfigFlow)
    assert flow._operation_task is not None
    await stopping.wait()
    hass.config_entries.flow.async_abort(result["flow_id"])
    try:
        await asyncio.sleep(0)
        flow._operation_task.cancel()
        await asyncio.sleep(0)
        assert not stop_cancelled.is_set()
        assert mock_besen_client.async_start.await_count == 1
        hub.async_stop.assert_not_awaited()
    finally:
        udp_client.async_stop.side_effect = None
        finish_stop.set()
        await asyncio.gather(flow._operation_task, return_exceptions=True)
        await hass.async_block_till_done()
        await async_release_udp_hub(hass)
    assert stopped.is_set()
    assert flow._operation_task.cancelled()
    assert mock_besen_client.async_start.await_count == 2
    hub.async_stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("source", "inputs"),
    [
        pytest.param(SOURCE_REAUTH, [{CONF_PIN: "654321"}], id="reauth"),
        pytest.param(
            SOURCE_RECONFIGURE,
            [{"next_step_id": "use_bluetooth"}, {CONF_PIN: "654321"}],
            id="reconfigure",
        ),
    ],
)
@pytest.mark.usefixtures("udp_client")
async def test_legacy_bluetooth_recovery_saves_serial_before_failed_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    device_registry: dr.DeviceRegistry,
    source: str,
    inputs: list[dict[str, str]],
) -> None:
    """Keep legacy serial identity when recovery succeeds but runtime setup fails."""
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    mock_besen_client.async_start.side_effect = [None, CannotConnect("setup failed")]
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    for user_input in inputs:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hasattr(mock_config_entry, "runtime_data")
    assert (
        dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
        == []
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert mock_config_entry.data[CONF_SERIAL] == SERIAL


@pytest.mark.parametrize(
    "stop_error",
    [
        pytest.param(CannotConnect("stop failed"), id="shutdown-raises"),
        pytest.param(None, id="still-connected"),
    ],
)
async def test_failed_cleanup_is_retried_before_restoring_saved_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    udp_client: Mock,
    hub: Mock,
    stop_error: Exception | None,
) -> None:
    """Keep one connection and recover retained resources during an entry reload."""
    mock_besen_client.state = udp_client.state
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    udp_client.is_connected = True
    udp_client.async_stop.side_effect = stop_error
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "lan"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert mock_besen_client.async_start.await_count == 1
    assert CONF_TRANSPORT not in mock_config_entry.data
    hub.async_stop.assert_not_awaited()
    udp_client.is_connected = False
    udp_client.async_stop.side_effect = None
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_besen_client.async_start.await_count == 2
    assert udp_client.async_stop.await_count == 2
    hub.async_stop.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_setup_retries_an_unreleased_validation_connection(
    hass: HomeAssistant, mock_besen_client: Mock
) -> None:
    """Retry retained Bluetooth cleanup before opening another validation client."""
    mock_besen_client.is_connected = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=FAKE_SERVICE_INFO
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: FIXTURE_PIN}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []
    mock_besen_client.is_connected = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: FIXTURE_PIN}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_besen_client.async_start.await_count == 2
    assert mock_besen_client.async_stop.await_count == 3


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        pytest.param(asyncio.CancelledError(), "cannot_connect", id="cancelled"),
        pytest.param(RuntimeError("task failed"), "unknown", id="unexpected-error"),
    ],
)
async def test_failed_progress_task_never_creates_an_entry(
    hass: HomeAssistant, failure: BaseException, expected: str
) -> None:
    """Return to the form when the background task cannot produce a valid result."""
    with patch(
        "homeassistant.components.besen.config_flow.BesenConfigFlow._test_connection",
        side_effect=failure,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert hass.config_entries.async_entries(DOMAIN) == []
    hass.config_entries.flow.async_abort(result["flow_id"])


@pytest.mark.parametrize(
    ("source", "inputs"),
    [
        pytest.param(SOURCE_REAUTH, [{CONF_PIN: "654321"}], id="reauth"),
        pytest.param(
            SOURCE_RECONFIGURE,
            [{"next_step_id": "use_bluetooth"}, {CONF_PIN: "654321"}],
            id="reconfigure",
        ),
    ],
)
async def test_legacy_recovery_rechecks_serial_before_saving(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    source: str,
    inputs: list[dict[str, str]],
) -> None:
    """Reject an identity another transport saved after recovery validation."""
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    for user_input in inputs:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert isinstance(flow, BesenConfigFlow)
    await flow._operation_task
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"lan:{SERIAL}",
        data={
            CONF_ADDRESS: f"lan:{SERIAL}",
            CONF_HOST: HOST,
            CONF_PIN: FIXTURE_PIN,
            CONF_SERIAL: SERIAL,
            CONF_TRANSPORT: "lan",
        },
    )
    other.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert CONF_SERIAL not in mock_config_entry.data
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN


async def test_changing_setup_host_cannot_bypass_retained_cleanup(
    hass: HomeAssistant,
    validation_clients: tuple[Mock, Mock],
    hub: Mock,
) -> None:
    """Close the previous candidate before trying a different setup address."""
    first, second = validation_clients
    first.async_stop.side_effect = CannotConnect("stop failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.20", CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    second.async_start.assert_not_awaited()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert first.async_stop.await_count == 2
    hub.async_stop.assert_not_awaited()
    first.async_stop.side_effect = None
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()


async def test_aborted_initial_setup_retries_retained_cleanup(
    hass: HomeAssistant, udp_client: Mock, hub: Mock
) -> None:
    """Release the last hub reference when failed setup is closed after recovery."""
    udp_client.async_stop.side_effect = CannotConnect("stop failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["errors"] == {"base": "cannot_connect"}
    udp_client.async_stop.side_effect = None
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert udp_client.async_stop.await_count == 2
    hub.async_stop.assert_awaited_once()
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("mock_setup_entry")
async def test_cleanup_retry_after_abort_remains_recoverable(
    hass: HomeAssistant, udp_client: Mock, hub: Mock
) -> None:
    """Recover retained cleanup when even the first post-abort retry fails."""
    udp_client.async_stop.side_effect = CannotConnect("stop failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["errors"] == {"base": "cannot_connect"}
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert udp_client.async_stop.await_count == 2
    hub.async_stop.assert_not_awaited()

    udp_client.async_stop.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert udp_client.async_start.await_count == 2
    assert udp_client.async_stop.await_count == 4
    assert hub.async_stop.await_count == 2


async def _cancelled_reconfigure_with_reauth_successor(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    current: Mock,
    candidate: Mock,
) -> ConfigFlowResult:
    """Open a new PIN form before cancelled validation reports restoration failure."""
    validating = asyncio.Event()
    restoring = asyncio.Event()
    finish_restore = asyncio.Event()

    async def wait_for_status(*, timeout: int) -> None:
        """Wait until the original Reconfigure flow is cancelled."""
        validating.set()
        await asyncio.Event().wait()

    async def restore() -> None:
        """Report the failure only after a successor flow has opened."""
        restoring.set()
        await finish_restore.wait()
        raise InvalidAuth("old PIN rejected")

    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    candidate.async_wait_for_status.side_effect = wait_for_status
    current.async_start.side_effect = restore
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "lan"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert isinstance(flow, BesenConfigFlow)
    await validating.wait()
    hass.config_entries.flow.async_abort(result["flow_id"])
    await restoring.wait()
    successor = await entry.start_reauth_flow(hass)
    current.async_start.side_effect = InvalidAuth("old PIN rejected")
    finish_restore.set()
    with pytest.raises(asyncio.CancelledError):
        await flow._operation_task
    await hass.async_block_till_done()
    return successor


async def test_replacement_reauth_survives_deferred_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    validation_clients: tuple[Mock, Mock],
) -> None:
    """Save the successor's verified PIN before an earlier retry can abort it."""
    first, second = validation_clients
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        result = await _cancelled_reconfigure_with_reauth_successor(
            hass, mock_config_entry, udp_client, first
        )
        reload.assert_not_awaited()
        assert result["flow_id"] in {
            item["flow_id"]
            for item in mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
        }
        with patch(
            "homeassistant.components.besen.BesenUdpClient", return_value=second
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_PIN: "654321"}
            )
            await hass.async_block_till_done()
            reload.assert_not_awaited()
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
            assert result["reason"] == "reauth_successful"
            await hass.async_block_till_done()
        reload.assert_awaited_once_with(mock_config_entry.entry_id)
    assert mock_config_entry.data[CONF_PIN] == "654321"
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is second


async def test_cancelling_replacement_reauth_retries_deferred_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    validation_clients: tuple[Mock, Mock],
) -> None:
    """Keep pending recovery when the successor PIN form is cancelled untouched."""
    first, _ = validation_clients
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        result = await _cancelled_reconfigure_with_reauth_successor(
            hass, mock_config_entry, udp_client, first
        )
        reload.assert_not_awaited()
        udp_client.async_start.side_effect = None
        hass.config_entries.flow.async_abort(result["flow_id"])
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(mock_config_entry.entry_id)
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_closing_overlapping_recovery_forms_queues_one_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    udp_client: Mock,
    validation_clients: tuple[Mock, Mock],
) -> None:
    """Discard duplicate queued recovery after both overlapping forms are closed."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_TRANSPORT: "lan",
            CONF_HOST: HOST,
            CONF_SERIAL: SERIAL,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    udp_client.async_start.side_effect = InvalidAuth("old PIN rejected")
    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        reauth = await mock_config_entry.start_reauth_flow(hass)
        reconfigure = await mock_config_entry.start_reconfigure_flow(hass)
        await hass.config_entries.flow.async_configure(
            reauth["flow_id"], {CONF_PIN: "654321"}
        )
        await hass.async_block_till_done()
        reload.assert_not_awaited()
        udp_client.async_start.side_effect = None
        hass.config_entries.flow.async_abort(reauth["flow_id"])
        hass.config_entries.flow.async_abort(reconfigure["flow_id"])
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_PIN] == FIXTURE_PIN


@pytest.mark.usefixtures("mock_setup_entry")
async def test_new_host_retry_resets_provisional_charger_identity(
    hass: HomeAssistant, validation_clients: tuple[Mock, Mock]
) -> None:
    """Allow a different charger after failed initial cleanup has recovered."""
    first, second = validation_clients
    second_serial = "1122334455667788"
    second_host = "192.0.2.20"
    second.state = second.state.updated(
        info=second.state.info.updated(serial=second_serial, model="Other BS20")
    )
    second.host = second_host
    first.async_stop.side_effect = CannotConnect("stop failed")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["errors"] == {"base": "cannot_connect"}
    first.async_stop.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: second_host, CONF_PIN: FIXTURE_PIN}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Other BS20"
    assert result["data"][CONF_SERIAL] == second_serial
    assert result["data"][CONF_ADDRESS] == f"lan:{second_serial}"
    assert result["data"][CONF_HOST] == second_host
    assert result["result"].unique_id == f"lan:{second_serial}"
    assert first.async_stop.await_count == 2
    second.async_start.assert_awaited_once()
    second.async_stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("source", "inputs"),
    [
        pytest.param(SOURCE_REAUTH, [{CONF_PIN: "654321"}], id="reauth"),
        pytest.param(
            SOURCE_RECONFIGURE,
            [{"next_step_id": "use_bluetooth"}, {CONF_PIN: "654321"}],
            id="reconfigure",
        ),
    ],
)
@pytest.mark.parametrize(
    ("known_data", "registry_serial"),
    [
        pytest.param({CONF_SERIAL: SERIAL}, None, id="saved-identity"),
        pytest.param({}, SERIAL, id="legacy-registry-identity"),
    ],
)
@pytest.mark.parametrize(
    ("reported_serial", "expected_error"),
    [
        pytest.param("1122334455667788", "wrong_device", id="different-serial"),
        pytest.param(None, "cannot_connect", id="missing-serial"),
    ],
)
async def test_bluetooth_recovery_rejects_mismatched_known_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    device_registry: dr.DeviceRegistry,
    source: str,
    inputs: list[dict[str, str]],
    known_data: dict[str, str],
    registry_serial: str | None,
    reported_serial: str | None,
    expected_error: str,
) -> None:
    """Preserve the saved charger binding when Bluetooth reports another serial."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, **known_data}
    )
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, FIXTURE_ADDRESS)},
        serial_number=registry_serial,
    )
    original = dict(mock_config_entry.data)
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=reported_serial)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    for user_input in inputs:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert mock_config_entry.data == original
    mock_besen_client.async_stop.assert_awaited_once()
    hass.config_entries.flow.async_abort(result["flow_id"])


@pytest.mark.parametrize(
    ("known_data", "registry_serial"),
    [
        pytest.param({CONF_SERIAL: SERIAL}, None, id="saved-identity"),
        pytest.param({}, SERIAL, id="legacy-registry-identity"),
    ],
)
async def test_startup_rejects_mismatched_saved_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    device_registry: dr.DeviceRegistry,
    known_data: dict[str, str],
    registry_serial: str | None,
) -> None:
    """Keep existing history unavailable instead of loading a different charger."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, **known_data}
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_BLUETOOTH, FIXTURE_ADDRESS)},
        serial_number=registry_serial,
    )
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial="1122334455667788")
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hasattr(mock_config_entry, "runtime_data")
    assert dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ) == [device]
    assert device_registry.async_get(device.id).serial_number == registry_serial
    mock_besen_client.async_stop.assert_awaited_once()


async def test_reconfigure_uses_runtime_identity_for_an_unrecorded_legacy_serial(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Learn current identity when neither legacy data nor the registry has it."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )[0]
    device_registry.async_update_device(device.id, serial_number=None)
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert isinstance(flow, BesenConfigFlow)
    assert flow._pending_data[CONF_SERIAL] == SERIAL
    assert CONF_SERIAL not in mock_config_entry.data
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_legacy_startup_rejects_another_configured_transport(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_besen_client: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Do not load an unidentified legacy entry for another entry's charger."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"lan:{SERIAL}",
        disabled_by=ConfigEntryDisabler.USER,
        data={
            CONF_ADDRESS: f"lan:{SERIAL}",
            CONF_HOST: HOST,
            CONF_PIN: FIXTURE_PIN,
            CONF_SERIAL: SERIAL,
            CONF_TRANSPORT: "lan",
        },
    )
    other.add_to_hass(hass)
    mock_besen_client.state = mock_besen_client.state.updated(
        info=mock_besen_client.state.info.updated(serial=SERIAL)
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hasattr(mock_config_entry, "runtime_data")
    assert (
        dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
        == []
    )
    mock_besen_client.async_stop.assert_awaited_once()
