"""Tests for Besen BS20 Home Assistant entities."""

from collections.abc import Callable
from dataclasses import replace
from typing import Any, ClassVar

from besen_bs20.models import BesenBS20Data, ChargerConfig, ChargerInfo, ChargeStatus
import pytest

from homeassistant.components import besen_bs20 as integration_module, bluetooth
from homeassistant.components.besen_bs20.const import CONF_SYNC_CLOCK, DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


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


class _FakeClient:
    """Fake Besen client."""

    instances: ClassVar[list[_FakeClient]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake client."""

        del args
        self.kwargs = kwargs
        self.address = kwargs["address"]
        self.state = _state()
        self.calls: list[str] = []
        self.listener: Callable[[BesenBS20Data], None] | None = None
        self.instances.append(self)

    def add_listener(
        self,
        listener: Callable[[BesenBS20Data], None],
    ) -> Callable[[], None]:
        """Record a listener."""

        self.listener = listener
        return lambda: None

    async def async_start(self) -> None:
        """Start the fake client."""

    async def async_stop(self) -> None:
        """Stop the fake client."""

    async def async_start_charging(self) -> None:
        """Record start charging and publish state."""

        self.calls.append("start_charging")
        self._publish_charging_state(True)

    async def async_stop_charging(self) -> None:
        """Record stop charging and publish state."""

        self.calls.append("stop_charging")
        self._publish_charging_state(False)

    def _publish_charging_state(self, charger_status: bool) -> None:
        """Publish an updated charging state."""

        self.state = replace(
            self.state,
            charge=replace(self.state.charge, charger_status=charger_status),
        )
        assert self.listener is not None
        self.listener(self.state)


def _entry() -> MockConfigEntry:
    """Return a config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB",
            CONF_NAME: "ACP#Garage",
            CONF_PIN: "123456",
        },
        options={CONF_SYNC_CLOCK: False},
        title="Garage",
        unique_id="AA:BB",
    )


async def test_charge_switch_entity(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switch exposes device info, state, and commands."""

    _FakeClient.instances = []
    monkeypatch.setattr(integration_module, "BesenBS20Client", _FakeClient)
    monkeypatch.setattr(
        bluetooth,
        "async_ble_device_from_address",
        lambda *args, **kwargs: object(),
    )

    entry = _entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    client = _FakeClient.instances[0]
    state = hass.states.get("switch.garage_charge")
    entity_entry = er.async_get(hass).async_get("switch.garage_charge")
    device_entry = dr.async_get(hass).async_get_device({(DOMAIN, "AA:BB")})

    assert state is not None
    assert state.state == STATE_ON
    assert entity_entry is not None
    assert entity_entry.unique_id == "AA:BB_charging"
    assert device_entry is not None
    assert device_entry.name == "Garage"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.garage_charge"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.garage_charge")
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.garage_charge"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.garage_charge")
    assert state is not None
    assert state.state == STATE_ON
    assert client.calls == ["stop_charging", "start_charging"]
