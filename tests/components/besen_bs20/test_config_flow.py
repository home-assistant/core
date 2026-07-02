"""Tests for Besen BS20 config flow."""

from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any, cast

from besen_bs20.exceptions import CannotConnect, InvalidAuth, NoConnectablePath
from besen_bs20.models import BesenBS20Data, ChargerInfo
from bleak.backends.device import BLEDevice
import pytest

from homeassistant.components.besen_bs20 import config_flow
from homeassistant.components.besen_bs20.config_flow import BesenBS20ConfigFlow
from homeassistant.components.besen_bs20.const import CONF_SYNC_CLOCK
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.data_entry_flow import FlowResultType


class _FakeConfigEntries:
    """Fake config entry manager."""

    def __init__(self, entry: SimpleNamespace) -> None:
        """Initialize the manager."""

        self.entry = entry
        self.reloads: list[str] = []

    def async_get_entry(self, entry_id: str) -> SimpleNamespace:
        """Return the configured fake entry."""

        del entry_id
        return self.entry

    def async_get_known_entry(self, entry_id: str) -> SimpleNamespace:
        """Return the configured fake entry."""

        return self.async_get_entry(entry_id)

    def async_update_entry(
        self,
        *,
        entry: SimpleNamespace,
        unique_id: object,
        title: object,
        data: dict[str, Any],
        options: dict[str, Any] | object,
    ) -> bool:
        """Update the fake entry."""

        del unique_id, title
        entry.data = data
        if isinstance(options, dict):
            entry.options = options
        return True

    def async_schedule_reload(self, entry_id: str) -> None:
        """Record scheduled reloads."""

        self.reloads.append(entry_id)


class _FakeValidationClient:
    """Fake client used by validation tests."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake client."""

        del args, kwargs
        self.state = BesenBS20Data(info=ChargerInfo(address="AA:BB", model="BS20"))
        self.started = False
        self.stopped = False

    async def async_start(self) -> None:
        """Record start."""

        self.started = True

    async def async_stop(self) -> None:
        """Record stop."""

        self.stopped = True


def _flow() -> BesenBS20ConfigFlow:
    """Return a config flow with a fake hass object."""

    flow = BesenBS20ConfigFlow()
    cast(Any, flow).hass = SimpleNamespace()
    cast(Any, flow).context = {}
    return flow


def _bluetooth_module() -> Any:
    """Return the runtime Bluetooth module imported by the config flow."""

    return cast(Any, config_flow).bluetooth


def _discovery(name: str | None = "ACP#Garage") -> Any:
    """Return fake Bluetooth discovery info."""

    return SimpleNamespace(name=name, address="aa:bb")


def _entry() -> SimpleNamespace:
    """Return a fake stored config entry."""

    return SimpleNamespace(
        entry_id="entry",
        data={CONF_ADDRESS: "AA:BB", CONF_NAME: "ACP#Garage", CONF_PIN: "123456"},
        options={CONF_SYNC_CLOCK: True},
        title="Garage",
        update_listeners=[],
    )


async def _validate_ok(*args: Any, **kwargs: Any) -> str:
    """Successful fake validation."""

    del args, kwargs
    return "Garage"


def _validation_raiser(exception: Exception) -> Callable[..., Awaitable[str]]:
    """Return a validator that raises the provided exception."""

    async def _raise(*args: Any, **kwargs: Any) -> str:
        del args, kwargs
        raise exception

    return _raise


async def _set_unique_id(unique_id: str) -> None:
    """Fake unique ID setter."""

    del unique_id


def _abort_if_unique_id_configured(*args: Any, **kwargs: Any) -> None:
    """Fake duplicate guard."""

    del args, kwargs


@pytest.mark.asyncio
async def test_validate_input_success_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation logs into the charger and reports setup errors."""

    monkeypatch.setattr(config_flow, "BesenBS20Client", _FakeValidationClient)
    monkeypatch.setattr(
        _bluetooth_module(),
        "async_ble_device_from_address",
        lambda *args, **kwargs: cast(BLEDevice, object()),
    )
    monkeypatch.setattr(
        _bluetooth_module(),
        "async_request_active_scan",
        _validate_ok,
        raising=False,
    )

    title = await config_flow._async_validate_input(
        cast(Any, object()),
        address="AA:BB",
        pin="123456",
        name=None,
        sync_clock=True,
    )

    assert title == "BS20"

    with pytest.raises(InvalidAuth):
        await config_flow._async_validate_input(
            cast(Any, object()),
            address="AA:BB",
            pin="12345",
            name=None,
            sync_clock=True,
        )

    monkeypatch.setattr(
        _bluetooth_module(),
        "async_ble_device_from_address",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(NoConnectablePath):
        await config_flow._async_validate_input(
            cast(Any, object()),
            address="AA:BB",
            pin="123456",
            name=None,
            sync_clock=True,
        )


@pytest.mark.asyncio
async def test_bluetooth_step_sets_discovered_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bluetooth discovery normalizes address and continues to confirmation."""

    flow = _flow()
    monkeypatch.setattr(flow, "async_set_unique_id", _set_unique_id)
    monkeypatch.setattr(
        flow,
        "_abort_if_unique_id_configured",
        _abort_if_unique_id_configured,
    )

    async def _confirm() -> dict[str, str]:
        return {"type": "confirm"}

    monkeypatch.setattr(flow, "async_step_bluetooth_confirm", _confirm)

    unsupported = await flow.async_step_bluetooth(_discovery("Other"))
    result = await flow.async_step_bluetooth(_discovery())

    assert unsupported["type"] is FlowResultType.ABORT
    assert unsupported["reason"] == "not_supported"
    assert result == {"type": "confirm"}
    assert flow._discovered_address == "AA:BB"
    assert flow._discovered_name == "ACP#Garage"
    assert flow.context["title_placeholders"] == {"name": "ACP#Garage"}


@pytest.mark.asyncio
async def test_bluetooth_confirm_success_and_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bluetooth confirmation creates entries or returns translated errors."""

    flow = _flow()
    flow._discovered_address = "AA:BB"
    flow._discovered_name = "ACP#Garage"

    form = await flow.async_step_bluetooth_confirm()
    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "bluetooth_confirm"

    monkeypatch.setattr(config_flow, "_async_validate_input", _validate_ok)
    result = await flow.async_step_bluetooth_confirm(
        {CONF_PIN: "123456", CONF_SYNC_CLOCK: False}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garage"
    assert result["data"][CONF_NAME] == "ACP#Garage"
    assert result["options"] == {CONF_SYNC_CLOCK: False}

    for exception, error in (
        (InvalidAuth("bad pin"), "invalid_auth"),
        (NoConnectablePath("no path"), "no_connectable_path"),
        (CannotConnect("cannot connect"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):

        async def _raise(
            *args: Any,
            exception: Exception = exception,
            **kwargs: Any,
        ) -> str:
            del args, kwargs
            raise exception

        monkeypatch.setattr(config_flow, "_async_validate_input", _raise)
        result = await flow.async_step_bluetooth_confirm(
            {CONF_PIN: "123456", CONF_SYNC_CLOCK: True}
        )
        assert result["errors"] == {"base": error}


@pytest.mark.asyncio
async def test_user_step_success_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manual setup handles success and validation errors."""

    flow = _flow()
    monkeypatch.setattr(flow, "async_set_unique_id", _set_unique_id)
    monkeypatch.setattr(
        flow,
        "_abort_if_unique_id_configured",
        _abort_if_unique_id_configured,
    )
    monkeypatch.setattr(config_flow, "_async_validate_input", _validate_ok)

    form = await flow.async_step_user()
    success = await flow.async_step_user(
        {
            CONF_ADDRESS: " aa:bb ",
            CONF_PIN: "123456",
            CONF_SYNC_CLOCK: True,
        }
    )

    assert form["type"] is FlowResultType.FORM
    assert form["step_id"] == "user"
    assert success["type"] is FlowResultType.CREATE_ENTRY
    assert success["data"][CONF_ADDRESS] == "AA:BB"
    assert success["options"] == {CONF_SYNC_CLOCK: True}

    for exception, error in (
        (InvalidAuth("bad pin"), "invalid_auth"),
        (NoConnectablePath("no path"), "no_connectable_path"),
        (CannotConnect("cannot connect"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        monkeypatch.setattr(
            config_flow,
            "_async_validate_input",
            _validation_raiser(exception),
        )
        result = await flow.async_step_user({CONF_ADDRESS: "AA:BB", CONF_PIN: "123456"})
        assert result["errors"] == {"base": error}


@pytest.mark.asyncio
async def test_reauth_and_reconfigure_flows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reauth and reconfigure update the entry after validation."""

    entry = _entry()
    reauth_flow = _flow()
    reauth_flow.context["entry_id"] = "entry"
    reauth_flow.context["source"] = SOURCE_REAUTH
    cast(Any, reauth_flow).hass = SimpleNamespace(
        config_entries=_FakeConfigEntries(entry)
    )

    reconfigure_flow = _flow()
    reconfigure_flow.context["entry_id"] = "entry"
    reconfigure_flow.context["source"] = SOURCE_RECONFIGURE
    cast(Any, reconfigure_flow).hass = SimpleNamespace(
        config_entries=_FakeConfigEntries(entry)
    )
    monkeypatch.setattr(config_flow, "_async_validate_input", _validate_ok)

    reauth_form = await reauth_flow.async_step_reauth(
        {CONF_ADDRESS: "AA:BB", CONF_NAME: "ACP#Garage"}
    )
    reauth_result = await reauth_flow.async_step_reauth_confirm({CONF_PIN: "654321"})
    reconfigure_form = await reconfigure_flow.async_step_reconfigure()
    reconfigure_result = await reconfigure_flow.async_step_reconfigure(
        {CONF_PIN: "654321", CONF_SYNC_CLOCK: False}
    )

    assert reauth_form["type"] is FlowResultType.FORM
    assert reauth_result["type"] is FlowResultType.ABORT
    assert reauth_result["reason"] == "reauth_successful"
    assert reconfigure_form["type"] is FlowResultType.FORM
    assert reconfigure_result["type"] is FlowResultType.ABORT
    assert reconfigure_result["reason"] == "reconfigure_successful"


@pytest.mark.asyncio
async def test_reauth_and_reconfigure_error_forms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reauth and reconfigure return errors from failed validation."""

    entry = _entry()
    reauth_flow = _flow()
    reauth_flow.context["entry_id"] = "entry"
    reauth_flow.context["source"] = SOURCE_REAUTH
    cast(Any, reauth_flow).hass = SimpleNamespace(
        config_entries=_FakeConfigEntries(entry)
    )

    reconfigure_flow = _flow()
    reconfigure_flow.context["entry_id"] = "entry"
    reconfigure_flow.context["source"] = SOURCE_RECONFIGURE
    cast(Any, reconfigure_flow).hass = SimpleNamespace(
        config_entries=_FakeConfigEntries(entry)
    )

    for exception, error in (
        (InvalidAuth("bad pin"), "invalid_auth"),
        (NoConnectablePath("no path"), "no_connectable_path"),
        (CannotConnect("cannot connect"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ):
        monkeypatch.setattr(
            config_flow,
            "_async_validate_input",
            _validation_raiser(exception),
        )
        reauth = await reauth_flow.async_step_reauth_confirm({CONF_PIN: "654321"})
        reconfigure = await reconfigure_flow.async_step_reconfigure(
            {CONF_PIN: "654321", CONF_SYNC_CLOCK: True}
        )

        assert reauth["errors"] == {"base": error}
        assert reconfigure["errors"] == {"base": error}
