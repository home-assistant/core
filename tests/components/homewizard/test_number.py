"""Test the update coordinator for HomeWizard."""
from unittest.mock import AsyncMock, patch

from homewizard_energy.errors import DisabledError, RequestError
from homewizard_energy.models import State
import pytest

from homeassistant.components import number
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .generator import get_mock_device


async def test_number_entity_not_loaded_when_not_available(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity does not load number when brightness is not available."""

    api = get_mock_device()

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get("number.product_name_aabbccddeeff_status_light_brightness")
        is None
    )


async def test_number_loads_entities(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity does load number when brightness is available."""

    api = get_mock_device()
    api.state = AsyncMock(return_value=State.from_dict({"brightness": 255}))

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    state = hass.states.get("number.product_name_aabbccddeeff_status_light_brightness")
    assert state
    assert state.state == "100"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Product Name (aabbccddeeff) Status light brightness"
    )

    entry = entity_registry.async_get(
        "number.product_name_aabbccddeeff_status_light_brightness"
    )
    assert entry
    assert entry.unique_id == "aabbccddeeff_status_light_brightness"
    assert not entry.disabled


async def test_brightness_level_set(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity turns sets light level."""

    api = get_mock_device()
    api.state = AsyncMock(return_value=State.from_dict({"brightness": 255}))

    def state_set(brightness):
        api.state = AsyncMock(return_value=State.from_dict({"brightness": brightness}))

    api.state_set = AsyncMock(side_effect=state_set)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get(
                "number.product_name_aabbccddeeff_status_light_brightness"
            ).state
            == "100"
        )

        # Set level halfway
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: (
                    "number.product_name_aabbccddeeff_status_light_brightness"
                ),
                ATTR_VALUE: 50,
            },
            blocking=True,
        )

        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "number.product_name_aabbccddeeff_status_light_brightness"
            ).state
            == "50"
        )
        assert len(api.state_set.mock_calls) == 1

        # Turn off level
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: (
                    "number.product_name_aabbccddeeff_status_light_brightness"
                ),
                ATTR_VALUE: 0,
            },
            blocking=True,
        )

        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "number.product_name_aabbccddeeff_status_light_brightness"
            ).state
            == "0"
        )
        assert len(api.state_set.mock_calls) == 2


async def test_brightness_level_set_catches_requesterror(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity raises HomeAssistantError when RequestError was raised."""

    api = get_mock_device()
    api.state = AsyncMock(return_value=State.from_dict({"brightness": 255}))

    api.state_set = AsyncMock(side_effect=RequestError())

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Set level halfway
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: (
                        "number.product_name_aabbccddeeff_status_light_brightness"
                    ),
                    ATTR_VALUE: 50,
                },
                blocking=True,
            )


async def test_brightness_level_set_catches_disablederror(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity raises HomeAssistantError when DisabledError was raised."""

    api = get_mock_device()
    api.state = AsyncMock(return_value=State.from_dict({"brightness": 255}))

    api.state_set = AsyncMock(side_effect=DisabledError())

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Set level halfway
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: (
                        "number.product_name_aabbccddeeff_status_light_brightness"
                    ),
                    ATTR_VALUE: 50,
                },
                blocking=True,
            )


async def test_brightness_level_set_catches_invalid_value(
    hass: HomeAssistant, mock_config_entry_data, mock_config_entry
) -> None:
    """Test entity raises ValueError when value was invalid."""

    api = get_mock_device()
    api.state = AsyncMock(return_value=State.from_dict({"brightness": 255}))

    def state_set(brightness):
        api.state = AsyncMock(return_value=State.from_dict({"brightness": brightness}))

    api.state_set = AsyncMock(side_effect=state_set)

    with patch(
        "homeassistant.components.homewizard.coordinator.HomeWizardEnergy",
        return_value=api,
    ):
        entry = mock_config_entry
        entry.data = mock_config_entry_data
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(ValueError):
            await hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: (
                        "number.product_name_aabbccddeeff_status_light_brightness"
                    ),
                    ATTR_VALUE: -1,
                },
                blocking=True,
            )

        with pytest.raises(ValueError):
            await hass.services.async_call(
                number.DOMAIN,
                SERVICE_SET_VALUE,
                {
                    ATTR_ENTITY_ID: (
                        "number.product_name_aabbccddeeff_status_light_brightness"
                    ),
                    ATTR_VALUE: 101,
                },
                blocking=True,
            )
