"""Constants for the Renault integration tests."""

from homeassistant.components.renault.const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

MOCK_ACCOUNT_ID = "account_id_1"

# Mock config data to be used across multiple tests
MOCK_CONFIG = {
    CONF_USERNAME: "email@test.com",
    CONF_PASSWORD: "test",
    CONF_KAMEREON_ACCOUNT_ID: MOCK_ACCOUNT_ID,
    CONF_LOCALE: "fr_FR",
}

MOCK_VEHICLES = {
    "zoe_40": {
        "endpoints": {
            "battery_status": "battery_status_charging.json",
            "charge_mode": "charge_mode_always.json",
            "cockpit": "cockpit_ev.json",
            "hvac_status": "hvac_status.1.json",
        },
    },
    "zoe_50": {
        "endpoints": {
            "battery_status": "battery_status_not_charging.json",
            "charge_mode": "charge_mode_schedule.json",
            "cockpit": "cockpit_ev.json",
            "hvac_status": "hvac_status.2.json",
            "location": "location.json",
            "lock_status": "lock_status.1.json",
            "res_state": "res_state.1.json",
        },
    },
    "captur_phev": {
        "endpoints": {
            "battery_status": "battery_status_charging.json",
            "charge_mode": "charge_mode_always.json",
            "cockpit": "cockpit_fuel.json",
            "location": "location.json",
            "lock_status": "lock_status.1.json",
            "res_state": "res_state.1.json",
        },
    },
    "captur_fuel": {
        "endpoints": {
            "cockpit": "cockpit_fuel.json",
            "location": "location.json",
            "lock_status": "lock_status.1.json",
            "res_state": "res_state.1.json",
        },
    },
    "twingo_3_electric": {
        "endpoints": {
            "battery_status": "battery_status_waiting_for_charger.json",
            "charge_mode": "charge_mode_always.2.json",
            "cockpit": "cockpit_ev.json",
            "hvac_status": "hvac_status.3.json",
            "location": "location.json",
        },
    },
}
