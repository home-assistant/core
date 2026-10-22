"""Constants for the Mealie integration."""

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
