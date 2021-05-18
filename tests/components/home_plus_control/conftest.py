"""Test setup and fixtures for component Home+ Control by Legrand."""
from homepluscontrol.homeplusinteractivemodule import HomePlusInteractiveModule
from homepluscontrol.homeplusplant import HomePlusPlant
import pytest

from homeassistant.components.home_plus_control.const import DOMAIN

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SUBSCRIPTION_KEY = "12345678901234567890123456789012"


@pytest.fixture()
def mock_config_entry():
    """Return a fake config entry.

    This is a minimal entry to setup the integration and to ensure that the
    OAuth access token will not expire.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home+ Control",
        data={
            "auth_implementation": "home_plus_control",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 9999999999,
                "expires_at": 9999999999.99999999,
                "expires_on": 9999999999,
            },
        },
        source="test",
        options={},
        system_options={"disable_new_entities": False},
        unique_id=DOMAIN,
        entry_id="home_plus_control_entry_id",
    )


@pytest.fixture()
def mock_modules():
    """Return the full set of mock modules."""
    plant = HomePlusPlant(
        id="123456789009876543210", name="My Home", country="ES", oauth_client=None
    )
    modules = {
        "0000000987654321fedcba": HomePlusInteractiveModule(
            plant,
            id="0000000987654321fedcba",
            name="Kitchen Wall Outlet",
            hw_type="NLP",
            device="plug",
            fw="42",
            reachable=True,
        ),
        "0000000887654321fedcba": HomePlusInteractiveModule(
            plant,
            id="0000000887654321fedcba",
            name="Bedroom Wall Outlet",
            hw_type="NLP",
            device="light",
            fw="42",
            reachable=True,
        ),
        "0000000787654321fedcba": HomePlusInteractiveModule(
            plant,
            id="0000000787654321fedcba",
            name="Living Room Ceiling Light",
            hw_type="NLF",
            device="light",
            fw="46",
            reachable=True,
        ),
        "0000000687654321fedcba": HomePlusInteractiveModule(
            plant,
            id="0000000687654321fedcba",
            name="Dining Room Ceiling Light",
            hw_type="NLF",
            device="light",
            fw="46",
            reachable=True,
        ),
        "0000000587654321fedcba": HomePlusInteractiveModule(
            plant,
            id="0000000587654321fedcba",
            name="Dining Room Wall Outlet",
            hw_type="NLP",
            device="plug",
            fw="42",
            reachable=True,
        ),
    }

    # Set lights off and plugs on
    for mod_stat in modules.values():
        mod_stat.status = "on"
        if mod_stat.device == "light":
            mod_stat.status = "off"

    return modules
