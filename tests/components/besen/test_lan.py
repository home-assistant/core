"""LAN setup, transport selection and shared listener regression coverage."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

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
    ConfigEntryState,
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
    mock_config_entry.runtime_data = Mock(client=mock_besen_client)
    flow = flow_for(hass, mock_config_entry)
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
    mock_config_entry.runtime_data = Mock(client=mock_besen_client)
    flow = flow_for(hass, mock_config_entry)
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


@pytest.mark.usefixtures("mock_besen_client")
async def test_bluetooth_switch_validates_before_saving(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that bluetooth switch validates before saving."""

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


async def test_reconfigure_recovers_identity_from_unloaded_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that reconfigure recovers identity from unloaded device."""

    mock_config_entry.add_to_hass(hass)
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
    mock_config_entry.runtime_data = Mock(client=mock_besen_client)
    flow = flow_for(hass, mock_config_entry)
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
    mock_besen_client.async_start.side_effect = CannotConnect("restore failed")
    mock_config_entry.runtime_data = Mock(client=mock_besen_client)
    flow = flow_for(hass, mock_config_entry)
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload:
        await flow.async_step_lan({CONF_HOST: HOST, CONF_PIN: FIXTURE_PIN})
        await flow._operation_task
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
