"""Tests for Besen BS20 data models."""

from besen_bs20.models import (
    BesenBS20Data,
    ChargerConfig,
    ChargerInfo,
    ChargeStatus,
    CommandResult,
)


def test_data_models_are_immutable_and_updatable() -> None:
    """Model update helpers return changed copies."""

    info = ChargerInfo(address="AA:BB", model="BS20")
    config = ChargerConfig(charge_amps=6)
    charge = ChargeStatus(charger_status=False)
    command = CommandResult(command="charge_start", values={"output_amps": 6})
    data = BesenBS20Data(
        info=info,
        config=config,
        charge=charge,
        last_command=command,
    )

    updated = data.updated(
        info=info.updated(serial="1234"),
        config=config.updated(charge_amps=10),
        charge=charge.updated(charger_status=True),
        available=True,
    )

    assert data.info.serial is None
    assert updated.info.serial == "1234"
    assert updated.config.charge_amps == 10
    assert updated.charge.charger_status is True
    assert updated.available is True
    assert updated.last_command == command
