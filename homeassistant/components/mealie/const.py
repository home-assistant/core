"""Constants for the Mealie integration."""

from enum import StrEnum
import logging

from awesomeversion import AwesomeVersion

DOMAIN = "mealie"

LOGGER = logging.getLogger(__package__)

CONF_PARSE_TODO_NEW = "parse_todo_new"
CONF_PARSE_TODO_EDIT = "parse_todo_edit"
CONF_PARSER = "parser"
DEFAULT_PARSER = "nlp"
MINIMUM_PARSER_CONFIDENCE = 0.98

MIN_REQUIRED_MEALIE_VERSION = AwesomeVersion("v3.2.0")


class MealieService(StrEnum):
    """Service names for Mealie."""

    ADD_INGREDIENT = "add_ingredient"
    DELETE_MEALPLAN = "delete_mealplan"
    GET_MEALPLAN = "get_mealplan"
    GET_RECIPE = "get_recipe"
    GET_RECIPES = "get_recipes"
    GET_SHOPPING_LIST_ITEMS = "get_shopping_list_items"
    IMPORT_RECIPE = "import_recipe"
    PARSE_INGREDIENT = "parse_ingredient"
    SET_MEALPLAN = "set_mealplan"
    SET_RANDOM_MEALPLAN = "set_random_mealplan"
    UPDATE_MEALPLAN = "update_mealplan"


class MealieServiceArgument(StrEnum):
    """Service argument names for Mealie."""

    END_DATE = "end_date"
    ENTRY_TYPE = "entry_type"
    FOOD_ID = "food_id"
    INCLUDE_TAGS = "include_tags"
    INGREDIENT = "ingredient"
    MEALPLAN_ID = "mealplan_id"
    NOTE = "note"
    NOTE_TEXT = "note_text"
    NOTE_TITLE = "note_title"
    QUANTITY = "quantity"
    RECIPE_ID = "recipe_id"
    RESULT_LIMIT = "result_limit"
    SEARCH_TERMS = "search_terms"
    START_DATE = "start_date"
    UNIT_ID = "unit_id"
    URL = "url"
