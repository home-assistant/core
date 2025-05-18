"""Tests for ScreenLogic climate entity."""

import logging
from unittest.mock import DEFAULT, patch

import pytest
from screenlogicpy import ScreenLogicGateway
from screenlogicpy.device_const.heat import HEAT_MODE

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from . import (
    DATA_MISSING_VALUES_CHEM_CHLOR,
    GATEWAY_DISCOVERY_IMPORT_PATH,
    MOCK_ADAPTER_NAME,
    stub_async_connect,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    (
        "tested_dataset",
        "expected_entity_states",
    ),
    [
        (
            DATA_MISSING_VALUES_CHEM_CHLOR,
            {
                f"{CLIMATE_DOMAIN}.{slugify(MOCK_ADAPTER_NAME)}_pool_heat": {
                    "state": HVACMode.OFF,
                    "attributes": {
                        ATTR_CURRENT_TEMPERATURE: 27.2,
                        ATTR_TEMPERATURE: 28.3,
                        ATTR_HVAC_ACTION: HVACAction.OFF,
                        ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT],
                        ATTR_PRESET_MODE: "heater",
                        ATTR_PRESET_MODES: [HEAT_MODE.HEATER.name.lower()],
                    },
                },
                f"{CLIMATE_DOMAIN}.{slugify(MOCK_ADAPTER_NAME)}_spa_heat": {
                    "state": HVACMode.HEAT,
                    "attributes": {
                        ATTR_CURRENT_TEMPERATURE: 28.9,
                        ATTR_TEMPERATURE: 34.4,
                        ATTR_HVAC_ACTION: HVACAction.IDLE,
                        ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT],
                        ATTR_PRESET_MODE: "heater",
                        ATTR_PRESET_MODES: [HEAT_MODE.HEATER.name.lower()],
                    },
                },
            },
        )
    ],
)
async def test_climate_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tested_dataset: dict,
    expected_entity_states: dict,
) -> None:
    """Test setup for platforms that define expected data."""

    def stub_connect(*args, **kwargs):
        return stub_async_connect(tested_dataset, *args, **kwargs)

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=stub_connect,
            is_connected=True,
            _async_connected_request=DEFAULT,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        for entity_id, state_data in expected_entity_states.items():
            assert (climate_state := hass.states.get(entity_id)) is not None
            assert climate_state.state == state_data["state"]
            for attribute, value in state_data["attributes"].items():
                assert climate_state.attributes[attribute] == value
