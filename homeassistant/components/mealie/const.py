"""Constants for the Mealie integration."""

from dataclasses import dataclass
import logging

from aiomealie import MealplanEntryType
from awesomeversion import AwesomeVersion

DOMAIN = "mealie"

LOGGER = logging.getLogger(__package__)

ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_RECIPE_ID = "recipe_id"
ATTR_URL = "url"
ATTR_INCLUDE_TAGS = "include_tags"
ATTR_ENTRY_TYPE = "entry_type"
ATTR_NOTE_TITLE = "note_title"
ATTR_NOTE_TEXT = "note_text"
ATTR_SEARCH_TERMS = "search_terms"
ATTR_RESULT_LIMIT = "result_limit"

MIN_REQUIRED_MEALIE_VERSION = AwesomeVersion("v1.0.0")


@dataclass
class MealTime:
    """class to store meal times."""

    text: str
    default: str


MEAL_TIME: dict[MealplanEntryType, MealTime] = {
    MealplanEntryType.BREAKFAST: MealTime("Breakfast Time", "9:00 AM"),
    MealplanEntryType.LUNCH: MealTime("Lunch Time", "12:00 PM"),
    MealplanEntryType.DINNER: MealTime("Dinner Time", "6:00 PM"),
    MealplanEntryType.SIDE: MealTime("Side Time", "5:00 PM"),
}
