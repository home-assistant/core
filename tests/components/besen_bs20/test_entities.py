"""Tests for Besen BS20 Home Assistant entities."""

from collections.abc import Callable
from typing import Any, cast

from besen_bs20.models import BesenBS20Data, ChargerConfig, ChargerInfo, ChargeStatus

from homeassistant.components.besen_bs20.coordinator import BesenBS20Coordinator
from homeassistant.components.besen_bs20.entity import BesenBS20Entity
from homeassistant.components.besen_bs20.switch import BesenBS20ChargeSwitch


class _FakeClient:
    """Fake client exposed by a coordinator."""

    def __init__(self, state: BesenBS20Data) -> None:
        """Initialize the fake client."""

        self.address = state.info.address
        self.state = state


class _FakeCoordinator:
    """Fake coordinator used by entities."""

    def __init__(self, data: BesenBS20Data | None) -> None:
        """Initialize the fake coordinator."""

        fallback = data or BesenBS20Data(info=ChargerInfo(address="AA:BB"))
        self.data = data
        self.client = _FakeClient(fallback)
        self.calls: list[str] = []
        self.last_update_success = True

    def async_add_listener(self, *args: Any, **kwargs: Any) -> Callable[[], None]:
        """Return a fake listener remover."""

        return lambda: None

    async def async_start_charging(self) -> None:
        """Record charge start."""

        self.calls.append("start")

    async def async_stop_charging(self) -> None:
        """Record charge stop."""

        self.calls.append("stop")


def _state(*, charger_status: bool | None = True) -> BesenBS20Data:
    """Return a populated available charger state."""

    return BesenBS20Data(
        info=ChargerInfo(
            address="AA:BB",
            serial="SERIAL",
            manufacturer="Besen",
            model="BS20",
            hardware_version="HW1",
            software_version="SW1",
        ),
        config=ChargerConfig(device_name="Garage"),
        charge=ChargeStatus(charger_status=charger_status),
        available=True,
        authenticated=True,
    )


def _coordinator(data: BesenBS20Data | None = None) -> BesenBS20Coordinator:
    """Return a fake coordinator cast to the integration coordinator type."""

    return cast(BesenBS20Coordinator, _FakeCoordinator(data))


def test_base_entity_device_info_and_availability() -> None:
    """Base entities expose device info and availability."""

    entity = BesenBS20Entity(_coordinator(_state()), "base")

    assert entity.available is True
    assert entity.unique_id == "AA:BB_base"
    assert entity.translation_key == "base"
    assert entity.device_info["name"] == "Garage"


async def test_charge_switch_state_and_commands() -> None:
    """Switch reads charging state and dispatches commands."""

    coordinator = _coordinator(_state())
    switch = BesenBS20ChargeSwitch(coordinator)

    assert switch.is_on is True
    assert switch.translation_key == "charging"

    await switch.async_turn_on()
    await switch.async_turn_off()

    assert cast(_FakeCoordinator, coordinator).calls == ["start", "stop"]
