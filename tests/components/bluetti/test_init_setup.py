"""Tests for async_setup_entry() in __init__.py."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.exceptions import ModbusConnectionError

from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "products": products or [],
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def test_async_setup_entry_with_no_devices(hass: HomeAssistant) -> None:
    """Async setup entry with no devices."""
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.bluetti_devices.devices == []
    assert entry.runtime_data.coordinators == {}
    assert entry.runtime_data.modbus_coordinators == {}
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_async_setup_entry_with_a_device(hass: HomeAssistant) -> None:
    """Async setup entry with a device."""
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    devices = entry.runtime_data.bluetti_devices.devices
    assert len(devices) == 1
    assert devices[0].device_id == "SN1"
    assert "SN1" in entry.runtime_data.coordinators
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_async_setup_entry_with_multiple_devices_refreshes_concurrently(
    hass: HomeAssistant,
) -> None:
    """Async setup entry with multiple devices refreshes concurrently."""
    # Each device's first refresh is run via asyncio.gather() instead of
    # sequentially, so setup time doesn't scale linearly with device count.
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Device 1", "stateList": [], "online": "1"},
            {"sn": "SN2", "name": "Device 2", "stateList": [], "online": "1"},
        ],
        devices=["SN1", "SN2"],
    )
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert set(coordinators.keys()) == {"SN1", "SN2"}
    assert all(c.last_update_success for c in coordinators.values())


async def test_async_setup_entry_reimports_missing_oauth_credential(
    hass: HomeAssistant,
) -> None:
    """Async setup entry reimports missing oauth credential."""
    # If the Application Credential backing the OAuth2 implementation was
    # ever lost (e.g. a partial backup restore), async_get_config_entry_
    # implementation raises ValueError("Implementation not available").
    # Setup should re-import the default credential and retry once instead
    # of failing forever.
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(
                side_effect=[ValueError("Implementation not available"), MagicMock()]
            ),
        ) as mock_get_impl,
        patch(
            "homeassistant.components.bluetti.async_ensure_default_credential",
            AsyncMock(),
        ) as mock_ensure_credential,
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    mock_ensure_credential.assert_awaited_once_with(hass)
    assert mock_get_impl.await_count == 2
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_async_setup_entry_retries_on_failure(hass: HomeAssistant) -> None:
    """Async setup entry retries on failure."""
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_retries_when_credential_stays_missing(
    hass: HomeAssistant,
) -> None:
    """Async setup entry retries when credential stays missing."""
    # Re-importing the default credential doesn't help if the underlying
    # cause isn't a missing credential (e.g. the application_credentials
    # component itself isn't ready yet) - setup should still fall back to
    # Home Assistant's normal ConfigEntryNotReady retry instead of raising.
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(side_effect=ValueError("Implementation not available")),
        ),
        patch(
            "homeassistant.components.bluetti.async_ensure_default_credential",
            AsyncMock(),
        ) as mock_ensure_credential,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_ensure_credential.assert_awaited_once_with(hass)


async def test_async_setup_entry_wires_up_modbus_coordinator_for_capable_device(
    hass: HomeAssistant,
) -> None:
    """Async setup entry wires up modbus coordinator for capable device."""
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
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
        patch("homeassistant.components.bluetti.async_get_unit") as mock_async_get_unit,
        patch("homeassistant.components.bluetti.get_device") as mock_get_device,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )
        modbus_device = MagicMock()
        modbus_device.async_update = AsyncMock()
        modbus_device._values = {}
        mock_get_device.return_value = modbus_device

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    mock_async_get_unit.assert_called_once()
    modbus_params = mock_async_get_unit.call_args.args[2]
    assert modbus_params.host == "10.2.1.60"
    assert modbus_params.port == 502
    mock_get_device.assert_called_once_with(
        "balco260", mock_async_get_unit.return_value
    )
    assert "SN1" in entry.runtime_data.modbus_coordinators
    assert entry.runtime_data.modbus_coordinators["SN1"].last_update_success


async def test_modbus_first_refresh_failure_does_not_prevent_cloud_entities_from_loading(
    hass: HomeAssistant,
) -> None:
    """Modbus first refresh failure does not prevent cloud entities from loading."""
    # Local Modbus is opt-in/supplementary - a hiccup here at startup must
    # not fail the whole config entry (and take the cloud entities down
    # with it). A failed first refresh should just leave that device's
    # Modbus entities unavailable until the coordinator's own next poll
    # succeeds, same as the cloud path already promises.
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
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
        patch("homeassistant.components.bluetti.async_get_unit"),
        patch("homeassistant.components.bluetti.get_device") as mock_get_device,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )
        modbus_device = MagicMock()
        modbus_device.async_update = AsyncMock(
            side_effect=ModbusConnectionError("no route to host")
        )
        mock_get_device.return_value = modbus_device

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert "SN1" in entry.runtime_data.coordinators
    assert entry.runtime_data.coordinators["SN1"].last_update_success
    assert not entry.runtime_data.modbus_coordinators["SN1"].last_update_success


async def test_unloading_the_entry_disconnects_the_websocket(
    hass: HomeAssistant,
) -> None:
    """Unloading the entry disconnects the websocket."""
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_stomp_cls.return_value.disconnect.assert_awaited_once()


async def test_a_failed_first_refresh_still_disconnects_the_websocket(
    hass: HomeAssistant,
) -> None:
    """A failed first refresh still disconnects the websocket, not just a full unload.

    Regression test: the websocket's disconnect must be registered via
    entry.async_on_unload() as soon as it connects, not only handled
    explicitly in async_unload_entry() - otherwise a first refresh failure
    (which puts the entry into a setup retry, not a full unload) would leave
    that websocket connection open, and each retry would connect a new one
    without ever disconnecting the last.
    """
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=RuntimeError("cloud is down")
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_stomp_cls.return_value.disconnect.assert_awaited_once()
