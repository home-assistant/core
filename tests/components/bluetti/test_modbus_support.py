"""Tests for the cloud-model-to-Modbus-device-type mapping."""

import pytest

from homeassistant.components.bluetti.modbus_support import modbus_dev_type_for_model


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("Balco260", "balco260"),
        ("EP2000", "ep2000"),
        ("balco260", "balco260"),
        # Real-world format observed via a real account's diagnostics dump:
        # "{model}-{custom device name from the BLUETTI phone app}". The
        # custom name is arbitrary - it happened to be "Balco260" here, but
        # must not be assumed to always match the model.
        ("Balco260-Balco260", "balco260"),
        ("Balco260-Chambre", "balco260"),
        ("EP2000-Garage", "ep2000"),
        ("SMeter", None),
        ("AC200L", None),
        # Regression test: only the part before the first hyphen (the real
        # model) is checked, not the whole string by containment - an
        # unsupported model must not be misclassified just because its
        # user-set custom name happens to contain a supported model's name.
        ("AC200L-EP2000", None),
        ("Unknown", None),
        ("", None),
        (None, None),
    ],
)
def test_modbus_dev_type_for_model(model, expected):
    """Modbus dev type for model."""
    assert modbus_dev_type_for_model(model) == expected
