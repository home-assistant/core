"""Utility functions."""

import re
from typing import Any


class RespUtil:
    """Utility functions for responses."""

    @staticmethod
    def convert_to_snake_case(data: dict[str, Any]) -> dict[str, str]:
        """Converts the dictionary's keys from camel naming to underscore naming."""

        def camel_to_snake(name: str) -> str:
            name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
            return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()

        return {camel_to_snake(k): v for k, v in data.items()}
