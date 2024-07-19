"""Tests for the Mealie services."""

from datetime import date
from unittest.mock import AsyncMock

from aiomealie.exceptions import (
    MealieConnectionError,
    MealieNotFoundError,
    MealieValidationError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.mealie.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END_DATE,
    ATTR_INCLUDE_TAGS,
    ATTR_RECIPE_ID,
    ATTR_START_DATE,
    ATTR_URL,
    DOMAIN,
)
from homeassistant.components.mealie.services import (
    SERVICE_GET_MEALPLAN,
    SERVICE_GET_RECIPE,
    SERVICE_IMPORT_RECIPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_service_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the get_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    freezer.move_to("2023-10-21")

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert mock_mealie_client.get_mealplans.call_args_list[1][0] == (
        date(2023, 10, 21),
        date(2023, 10, 21),
    )
    assert response == snapshot

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_START_DATE: "2023-10-22",
            ATTR_END_DATE: "2023-10-25",
        },
        blocking=True,
        return_response=True,
    )
    assert response
    assert mock_mealie_client.get_mealplans.call_args_list[2][0] == (
        date(2023, 10, 22),
        date(2023, 10, 25),
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_START_DATE: "2023-10-19",
        },
        blocking=True,
        return_response=True,
    )
    assert response
    assert mock_mealie_client.get_mealplans.call_args_list[3][0] == (
        date(2023, 10, 19),
        date(2023, 10, 21),
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_END_DATE: "2023-10-22",
        },
        blocking=True,
        return_response=True,
    )
    assert response
    assert mock_mealie_client.get_mealplans.call_args_list[4][0] == (
        date(2023, 10, 21),
        date(2023, 10, 22),
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_START_DATE: "2023-10-22",
                ATTR_END_DATE: "2023-10-19",
            },
            blocking=True,
            return_response=True,
        )


async def test_service_recipe(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_recipe service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_RECIPE,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, ATTR_RECIPE_ID: "recipe_id"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_service_import_recipe(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the import_recipe service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_URL: "http://example.com",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.import_recipe.assert_called_with(
        "http://example.com", include_tags=False
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_IMPORT_RECIPE,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_URL: "http://example.com",
            ATTR_INCLUDE_TAGS: True,
        },
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.import_recipe.assert_called_with(
        "http://example.com", include_tags=True
    )


@pytest.mark.parametrize(
    ("exception", "raised_exception"),
    [
        (MealieNotFoundError, ServiceValidationError),
        (MealieConnectionError, HomeAssistantError),
    ],
)
async def test_service_recipe_exceptions(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    raised_exception: type[Exception],
) -> None:
    """Test the get_recipe service."""

    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.get_recipe.side_effect = exception

    with pytest.raises(raised_exception):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_RECIPE,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_RECIPE_ID: "recipe_id",
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("exception", "raised_exception"),
    [
        (MealieValidationError, ServiceValidationError),
        (MealieConnectionError, HomeAssistantError),
    ],
)
async def test_service_import_recipe_exceptions(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    raised_exception: type[Exception],
) -> None:
    """Test the exceptions of the import_recipe service."""

    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.import_recipe.side_effect = exception

    with pytest.raises(raised_exception):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IMPORT_RECIPE,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_URL: "http://example.com",
            },
            blocking=True,
            return_response=True,
        )


async def test_service_mealplan_connection_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection error in the get_mealplans service."""

    await setup_integration(hass, mock_config_entry)

    mock_mealie_client.get_mealplans.side_effect = MealieConnectionError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
            blocking=True,
            return_response=True,
        )


async def test_service_mealplan_without_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the get_mealplan service without entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_MEALPLAN,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"},
            blocking=True,
            return_response=True,
        )
