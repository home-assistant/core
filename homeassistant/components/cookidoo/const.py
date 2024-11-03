"""Constants for the Cookidoo integration."""

from typing import Final

DOMAIN = "cookidoo"

CONF_LOCALIZATION: Final = "localization"

LOCALIZATION_SPLIT_CHAR: Final = "_"
DEFAULT_LOCALIZATION: Final = LOCALIZATION_SPLIT_CHAR.join(["ch", "de-CH"]).lower()

TODO_INGREDIENTS: Final = "ingredients"
TODO_ADDITIONAL_ITEMS: Final = "additional_items"
