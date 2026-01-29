"""Test the Nina services."""

from unittest.mock import AsyncMock

from homeassistant.components.nina.const import (
    DOMAIN,
    SERVICE_GET_AFFECTED_AREAS,
    SERVICE_GET_DESCRIPTION,
    SERVICE_GET_RECOMMENDED_ACTIONS,
)
from homeassistant.const import ATTR_ENTITY_ID, MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant

from . import setup_platform, setup_single_platform

from tests.common import MockConfigEntry


async def test_service_registration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nina_class: AsyncMock
) -> None:
    """Test the NINA services be registered."""
    await setup_single_platform(hass, mock_config_entry, None, mock_nina_class, [])

    services = hass.services.async_services_for_domain(DOMAIN)

    assert len(services) == 3
    assert SERVICE_GET_DESCRIPTION in services
    assert SERVICE_GET_AFFECTED_AREAS in services
    assert SERVICE_GET_RECOMMENDED_ACTIONS in services


async def test_description_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test that the get descriptions service return the description."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    target_entity_id = "binary_sensor.nina_warning_aach_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DESCRIPTION,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert (
        result[target_entity_id]
        == "Es treten Sturmböen mit Geschwindigkeiten zwischen 70 km/h (20m/s, 38kn, Bft 8) und 85 km/h (24m/s, 47kn, Bft 9) aus westlicher Richtung auf. In Schauernähe sowie in exponierten Lagen muss mit schweren Sturmböen bis 90 km/h (25m/s, 48kn, Bft 10) gerechnet werden."
    )


async def test_description_service_no_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
) -> None:
    """Test that the get descriptions service return None if no warning is present."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, [])

    target_entity_id = "binary_sensor.nina_warning_aach_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DESCRIPTION,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert result[target_entity_id] is None


async def test_affected_area_service_full_description(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test that the get affected area service return the full area."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    target_entity_id = "binary_sensor.nina_warning_aach_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_AFFECTED_AREAS,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert (
        result[target_entity_id]
        == "Gemeinde Oberreichenbach, Gemeinde Neuweiler, Stadt Nagold, Stadt Neubulach, Gemeinde Schömberg, Gemeinde Simmersfeld, Gemeinde Simmozheim, Gemeinde Rohrdorf, Gemeinde Ostelsheim, Gemeinde Ebhausen, Gemeinde Egenhausen, Gemeinde Dobel, Stadt Bad Liebenzell, Stadt Solingen, Stadt Haiterbach, Stadt Bad Herrenalb, Gemeinde Höfen an der Enz, Gemeinde Gechingen, Gemeinde Enzklösterle, Gemeinde Gutach (Schwarzwaldbahn) und 3392 weitere."
    )

    assert len(result[target_entity_id]) > MAX_LENGTH_STATE_STATE


async def test_affected_area_service_no_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
) -> None:
    """Test that the get affected area service return None if no warning is present."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, [])

    target_entity_id = "binary_sensor.nina_warning_aach_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_AFFECTED_AREAS,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert result[target_entity_id] is None


async def test_recommended_actions_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test that the get recommended actions service return the full area."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    target_entity_id = "binary_sensor.nina_warning_aach_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_RECOMMENDED_ACTIONS,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert (
        result[target_entity_id]
        == "ACHTUNG! Hinweis auf mögliche Gefahren: Es können zum Beispiel einzelne Äste herabstürzen. Achte besonders auf herabfallende Gegenstände."
    )


async def test_recommended_actions_service_no_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
) -> None:
    """Test that the get recommended actions service return None if no warning is present."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, [])

    target_entity_id = "binary_sensor.nina_warning_aach_1"

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_RECOMMENDED_ACTIONS,
        {ATTR_ENTITY_ID: target_entity_id},
        blocking=True,
        return_response=True,
    )

    assert result[target_entity_id] is None
