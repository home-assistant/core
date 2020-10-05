"""Test the SRP Energy config flow."""


import pytest

from homeassistant import data_entry_flow
from homeassistant.components import srp_energy
from homeassistant.components.srp_energy.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(name="mock_setup")
def mock_setup():
    """Mock entry setup."""
    with patch(
        "homeassistant.components.srp_energy.async_setup_entry",
        return_value=True,
    ):
        yield


# async def test_flow_works(hass, mock_setup):
#     """Test user config."""
#     result = await hass.config_entries.flow.async_init(
#         srp_energy.DOMAIN, context={"source": "user"}
#     )
#     assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
#     assert result["step_id"] == "user"


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        srp_energy.DOMAIN, context={"source": "user"}
    )
    print("Here we go")
    print(result["reason"])
    print("there it is")
    print(data_entry_flow.RESULT_TYPE_ABORT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"
