"""Defines the NutCommand class for representing NUT commands and their parameters."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import voluptuous as vol


@dataclass
class NutParameter:
    """Class for representing NUT command parameters with a name and schema, as well as a method for converting the param into a string."""

    name: str
    schema: vol.All
    string_formatting_callback: Callable[[Any], str]


@dataclass
class NutCommand:
    """Class for representing NUT commands."""

    command_string: str
    parameter: NutParameter | None = None
