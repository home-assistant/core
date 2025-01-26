"""Tests for the Flick Electric integration."""

from pyflick.types import FlickPrice

from homeassistant.components.flick_electric.const import (
    CONF_ACCOUNT_ID,
    CONF_SUPPLY_NODE_REF,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

CONF = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_ACCOUNT_ID: "1234",
    CONF_SUPPLY_NODE_REF: "123",
}


def _mock_flick_price():
    return FlickPrice(
        {
            "cost": "0.25",
            "quantity": "1.0",
            "status": "final",
            "start_at": "2024-01-01T00:00:00Z",
            "end_at": "2024-01-01T00:00:00Z",
            "type": "flat",
            "components": [
                {
                    "charge_method": "kwh",
                    "charge_setter": "network",
                    "value": "1.00",
                    "single_unit_price": "1.00",
                    "quantity": "1.0",
                    "unit_code": "NZD",
                    "charge_per": "kwh",
                    "flow_direction": "import",
                },
                {
                    "charge_method": "kwh",
                    "charge_setter": "nonsupported",
                    "value": "1.00",
                    "single_unit_price": "1.00",
                    "quantity": "1.0",
                    "unit_code": "NZD",
                    "charge_per": "kwh",
                    "flow_direction": "import",
                },
            ],
        }
    )
