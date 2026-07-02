"""Tests for Besen BS20 config flow."""

from collections.abc import Generator
from typing import Any, ClassVar
from unittest.mock import AsyncMock, patch

from besen_bs20.exceptions import CannotConnect, InvalidAuth
from besen_bs20.models import BesenBS20Data, ChargerInfo
import pytest

from homeassistant.components.besen_bs20 import config_flow
from homeassistant.components.besen_bs20.const import CONF_SYNC_CLOCK, DOMAIN
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


class _FakeValidationClient:
    """Fake client used by validation tests."""

    instances: ClassVar[list[_FakeValidationClient]] = []
    next_error: ClassVar[Exception | None] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake client."""

        del args
        self.kwargs = kwargs
        self.state = BesenBS20Data(info=ChargerInfo(address="AA:BB", model="BS20"))
        self.started = False
        self.stopped = False
        self.instances.append(self)

    async def async_start(self) -> None:
        """Record start or raise a configured error."""

        if self.next_error is not None:
            raise self.next_error
        self.started = True

    async def async_stop(self) -> None:
        """Record stop."""

        self.stopped = True


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock integration setup after a config flow creates an entry."""

    with patch(
        "homeassistant.components.besen_bs20.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_validation_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock BLE validation dependencies."""

    _FakeValidationClient.instances = []
    _FakeValidationClient.next_error = None
    monkeypatch.setattr(config_flow, "BesenBS20Client", _FakeValidationClient)
    monkeypatch.setattr(
        config_flow.bluetooth,
        "async_ble_device_from_address",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        config_flow.bluetooth,
        "async_request_active_scan",
        AsyncMock(),
    )


def _discovery(name: str | None = "ACP#Garage") -> BluetoothServiceInfoBleak:
    """Return Bluetooth discovery info."""

    return BluetoothServiceInfoBleak(
        name=name,
        address="aa:bb",
        rssi=-60,
        manufacturer_data={},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="aa:bb", name=name),
        advertisement=generate_advertisement_data(
            local_name=name,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )


async def test_bluetooth_step_sets_discovered_context(
    hass: HomeAssistant,
) -> None:
    """Bluetooth discovery normalizes address and continues to confirmation."""

    unsupported = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery("Other"),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )

    assert unsupported["type"] is FlowResultType.ABORT
    assert unsupported["reason"] == "not_supported"
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_bluetooth_confirm_success(hass: HomeAssistant) -> None:
    """Bluetooth confirmation creates an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "123456", CONF_SYNC_CLOCK: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BS20"
    assert result["data"][CONF_ADDRESS] == "AA:BB"
    assert result["data"][CONF_NAME] == "ACP#Garage"
    assert result["options"] == {CONF_SYNC_CLOCK: False}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(InvalidAuth("bad pin"), "invalid_auth", id="invalid-auth"),
        pytest.param(CannotConnect("cannot connect"), "cannot_connect", id="connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
async def test_bluetooth_confirm_errors(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
) -> None:
    """Bluetooth confirmation returns translated validation errors."""

    _FakeValidationClient.next_error = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "123456", CONF_SYNC_CLOCK: True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_bluetooth_confirm_no_connectable_path(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bluetooth confirmation returns an error when no active path exists."""

    monkeypatch.setattr(
        config_flow.bluetooth,
        "async_ble_device_from_address",
        lambda *args, **kwargs: None,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery(),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "123456", CONF_SYNC_CLOCK: True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_connectable_path"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_success(hass: HomeAssistant) -> None:
    """Manual setup creates an entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ADDRESS: " aa:bb ",
            CONF_PIN: "123456",
            CONF_SYNC_CLOCK: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BS20"
    assert result["data"][CONF_ADDRESS] == "AA:BB"
    assert result["options"] == {CONF_SYNC_CLOCK: True}


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(InvalidAuth("bad pin"), "invalid_auth", id="invalid-auth"),
        pytest.param(CannotConnect("cannot connect"), "cannot_connect", id="connect"),
        pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    exception: Exception,
    error: str,
) -> None:
    """Manual setup returns translated validation errors."""

    _FakeValidationClient.next_error = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: "AA:BB", CONF_PIN: "123456"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_user_step_no_connectable_path(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual setup returns an error when no active path exists."""

    monkeypatch.setattr(
        config_flow.bluetooth,
        "async_ble_device_from_address",
        lambda *args, **kwargs: None,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ADDRESS: "AA:BB", CONF_PIN: "123456"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_connectable_path"}
