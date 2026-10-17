"""Define tests for the Airzone init."""

from unittest.mock import patch

from aioairzone.const import DEFAULT_SYSTEM_ID
from aioairzone.exceptions import HotWaterNotAvailable, InvalidMethod, SystemOutOfRange

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import (
    CONFIG,
    HVAC_MOCK,
    HVAC_VERSION_MOCK,
    HVAC_WEBSERVER_MOCK,
    USER_INPUT,
    async_init_integration,
)

from tests.common import MockConfigEntry


async def test_unique_id_migrate(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique id migration."""

    config_entry = MockConfigEntry(
        minor_version=2,
        domain=DOMAIN,
        data=CONFIG,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
            side_effect=HotWaterNotAvailable,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
            return_value=HVAC_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
            side_effect=SystemOutOfRange,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_version",
            return_value=HVAC_VERSION_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
            side_effect=InvalidMethod,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert not config_entry.unique_id
    assert (
        entity_registry.async_get("sensor.salon_temperature").unique_id
        == f"{config_entry.entry_id}_1:1_temp"
    )

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
            side_effect=HotWaterNotAvailable,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
            return_value=HVAC_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
            side_effect=SystemOutOfRange,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_version",
            return_value=HVAC_VERSION_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
            return_value=HVAC_WEBSERVER_MOCK,
        ),
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
        minor_version=2,
        data=CONFIG,
        domain=DOMAIN,
        unique_id="airzone_unique_id",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.validate",
            return_value=None,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.update",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_via_device_links(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that child devices link to their registered parent via via_device_id."""

    config_entry = await async_init_integration(hass)

    ws_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}_ws"), config_entry.entry_id
    )
    assert ws_device is not None

    system_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}_1"), config_entry.entry_id
    )
    assert system_device is not None
    assert system_device.via_device_id == ws_device.id

    zone_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}_1:1"), config_entry.entry_id
    )
    assert zone_device is not None
    assert zone_device.via_device_id == system_device.id


async def test_migrate_entry_v2(hass: HomeAssistant) -> None:
    """Test entry migration to v2."""

    config_entry = MockConfigEntry(
        minor_version=1,
        data=USER_INPUT,
        domain=DOMAIN,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
            side_effect=HotWaterNotAvailable,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
            return_value=HVAC_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
            side_effect=SystemOutOfRange,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_version",
            return_value=HVAC_VERSION_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
            side_effect=InvalidMethod,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.minor_version == 2
    assert config_entry.data.get(CONF_ID) == DEFAULT_SYSTEM_ID
