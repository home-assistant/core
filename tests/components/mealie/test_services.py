"""Tests for the Mealie services."""

from datetime import date
from unittest.mock import AsyncMock

from aiomealie import (
    MealieConnectionError,
    MealieNotFoundError,
    MealieValidationError,
    MealplanEntryType,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.mealie.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_END_DATE,
    ATTR_ENTRY_TYPE,
    ATTR_INCLUDE_TAGS,
    ATTR_NOTE_TEXT,
    ATTR_NOTE_TITLE,
    ATTR_RECIPE_ID,
    ATTR_START_DATE,
    ATTR_URL,
    DOMAIN,
)
from homeassistant.components.mealie.services import (
    SERVICE_GET_MEALPLAN,
    SERVICE_GET_RECIPE,
    SERVICE_IMPORT_RECIPE,
    SERVICE_SET_MEALPLAN,
    SERVICE_SET_RANDOM_MEALPLAN,
)
from homeassistant.const import ATTR_DATE
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


async def test_service_set_random_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the set_random_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RANDOM_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.random_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH
    )

    mock_mealie_client.random_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RANDOM_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        },
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.random_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH
    )


@pytest.mark.parametrize(
    ("payload", "kwargs"),
    [
        (
            {
                ATTR_RECIPE_ID: "recipe_id",
            },
            {"recipe_id": "recipe_id", "note_title": None, "note_text": None},
        ),
        (
            {
                ATTR_NOTE_TITLE: "Note Title",
                ATTR_NOTE_TEXT: "Note Text",
            },
            {"recipe_id": None, "note_title": "Note Title", "note_text": "Note Text"},
        ),
    ],
)
async def test_service_set_mealplan(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    payload: dict[str, str],
    kwargs: dict[str, str],
) -> None:
    """Test the set_mealplan service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    mock_mealie_client.set_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )

    mock_mealie_client.random_mealplan.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MEALPLAN,
        {
            ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_DATE: "2023-10-21",
            ATTR_ENTRY_TYPE: "lunch",
        }
        | payload,
        blocking=True,
        return_response=False,
    )
    mock_mealie_client.set_mealplan.assert_called_with(
        date(2023, 10, 21), MealplanEntryType.LUNCH, **kwargs
    )


@pytest.mark.parametrize(
    ("service", "payload", "function", "exception", "raised_exception", "message"),
    [
        (
            SERVICE_GET_MEALPLAN,
            {},
            "get_mealplans",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
        ),
        (
            SERVICE_GET_RECIPE,
            {ATTR_RECIPE_ID: "recipe_id"},
            "get_recipe",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
        ),
        (
            SERVICE_GET_RECIPE,
            {ATTR_RECIPE_ID: "recipe_id"},
            "get_recipe",
            MealieNotFoundError,
            ServiceValidationError,
            "Recipe with ID or slug `recipe_id` not found",
        ),
        (
            SERVICE_IMPORT_RECIPE,
            {ATTR_URL: "http://example.com"},
            "import_recipe",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
        ),
        (
            SERVICE_IMPORT_RECIPE,
            {ATTR_URL: "http://example.com"},
            "import_recipe",
            MealieValidationError,
            ServiceValidationError,
            "Mealie could not import the recipe from the URL",
        ),
        (
            SERVICE_SET_RANDOM_MEALPLAN,
            {ATTR_DATE: "2023-10-21", ATTR_ENTRY_TYPE: "lunch"},
            "random_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
        ),
        (
            SERVICE_SET_MEALPLAN,
            {
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
            "set_mealplan",
            MealieConnectionError,
            HomeAssistantError,
            "Error connecting to Mealie instance",
        ),
    ],
)
async def test_services_connection_error(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
    function: str,
    exception: Exception,
    raised_exception: type[Exception],
    message: str,
) -> None:
    """Test a connection error in the services."""

    await setup_integration(hass, mock_config_entry)

    getattr(mock_mealie_client, function).side_effect = exception

    with pytest.raises(raised_exception, match=message):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id} | payload,
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service", "payload"),
    [
        (SERVICE_GET_MEALPLAN, {}),
        (SERVICE_GET_RECIPE, {ATTR_RECIPE_ID: "recipe_id"}),
        (SERVICE_IMPORT_RECIPE, {ATTR_URL: "http://example.com"}),
        (
            SERVICE_SET_RANDOM_MEALPLAN,
            {ATTR_DATE: "2023-10-21", ATTR_ENTRY_TYPE: "lunch"},
        ),
        (
            SERVICE_SET_MEALPLAN,
            {
                ATTR_DATE: "2023-10-21",
                ATTR_ENTRY_TYPE: "lunch",
                ATTR_RECIPE_ID: "recipe_id",
            },
        ),
    ],
)
async def test_service_entry_availability(
    hass: HomeAssistant,
    mock_mealie_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    payload: dict[str, str],
) -> None:
    """Test the services without valid entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2 = MockConfigEntry(domain=DOMAIN)
    mock_config_entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Mock Title is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry2.entry_id} | payload,
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        ServiceValidationError, match='Integration "mealie" not found in registry'
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_CONFIG_ENTRY_ID: "bad-config_id"} | payload,
            blocking=True,
            return_response=True,
        )
