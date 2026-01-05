"""Test Kostal Plenticore number."""

from datetime import timedelta

from pykoplenti import ApiClient, SettingsData
import pytest

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = [
    pytest.mark.usefixtures("mock_plenticore_client"),
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_all_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if all available entries are setup."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("number.scb_battery_min_soc") is not None
    assert (
        entity_registry.async_get("number.scb_battery_min_home_consumption") is not None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_no_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_get_settings: dict[str, list[SettingsData]],
) -> None:
    """Test that no entries are setup if Plenticore does not provide data."""

    # remove all settings except hostname which is used during setup
    mock_get_settings.clear()
    mock_get_settings.update(
        {
            "scb:network": [
                SettingsData(
                    min="1",
                    max="63",
                    default=None,
                    access="readwrite",
                    unit=None,
                    id="Hostname",
                    type="string",
                )
            ]
        }
    )

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("number.scb_battery_min_soc") is None
    assert entity_registry.async_get("number.scb_battery_min_home_consumption") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_has_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if number has a value if data is provided on update."""

    mock_get_setting_values["devices:local"]["Battery:MinSoc"] = "42"

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    state = hass.states.get("number.scb_battery_min_soc")
    assert state.state == "42"
    assert state.attributes[ATTR_MIN] == 5
    assert state.attributes[ATTR_MAX] == 100


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if number is unavailable if no data is provided on update."""

    del mock_get_setting_values["devices:local"]["Battery:MinSoc"]

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    state = hass.states.get("number.scb_battery_min_soc")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if a new value could be set."""

    mock_get_setting_values["devices:local"]["Battery:MinSoc"] = "42"

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.scb_battery_min_soc",
            ATTR_VALUE: 80,
        },
        blocking=True,
    )

    mock_plenticore_client.set_setting_values.assert_called_once_with(
        "devices:local", {"Battery:MinSoc": "80"}
    )
