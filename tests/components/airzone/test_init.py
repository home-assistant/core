"""Define tests for the Airzone init."""

from unittest.mock import patch

from aioairzone.exceptions import HotWaterNotAvailable, InvalidMethod, SystemOutOfRange

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .util import CONFIG, HVAC_MOCK, HVAC_VERSION_MOCK, HVAC_WEBSERVER_MOCK

from tests.common import MockConfigEntry


async def test_unique_id_migrate(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id migration."""

    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
        side_effect=HotWaterNotAvailable,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        side_effect=SystemOutOfRange,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_version",
        return_value=HVAC_VERSION_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        side_effect=InvalidMethod,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert not config_entry.unique_id
    assert (
        entity_registry.async_get("sensor.salon_temperature").unique_id
        == f"{config_entry.entry_id}_1:1_temp"
    )

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
        side_effect=HotWaterNotAvailable,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
        return_value=HVAC_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
        side_effect=SystemOutOfRange,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_version",
        return_value=HVAC_VERSION_MOCK,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
        return_value=HVAC_WEBSERVER_MOCK,
    ):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.unique_id
    assert (
        entity_registry.async_get("sensor.salon_temperature").unique_id
        == f"{config_entry.unique_id}_1:1_temp"
    )


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
        unique_id="airzone_unique_id",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airzone.AirzoneLocalApi.validate",
        return_value=None,
    ), patch(
        "homeassistant.components.airzone.AirzoneLocalApi.update",
        return_value=None,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
