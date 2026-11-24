"""Common helpers for the config tests."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any, Literal

import probatio

from homeassistant.helpers.script import _BLOCK_SCHEMAS
from homeassistant.helpers.validation_errors import iter_validation_errors

type BlockKind = Literal["triggers", "conditions", "actions"]


def assert_error_paths_resolve(submitted: Any, errors: list[dict[str, Any]]) -> None:
    """Assert the path of each error is a path in the submitted config.

    The last segment of a path may be a key which is missing in the config.
    """
    for error in errors:
        path = error["path"]
        value = submitted
        for index, segment in enumerate(path):
            assert isinstance(value, (dict, list)), (path, index)
            if isinstance(value, list):
                assert isinstance(segment, int), (path, index)
                assert 0 <= segment < len(value), (path, index)
            elif segment not in value:
                # Only the last segment may be a missing key
                assert index == len(path) - 1, (path, index)
                break
            value = value[segment]


def _schema_errors(
    schema: Callable[[Any], Any], value: Any
) -> list[tuple[tuple[Any, ...], str]]:
    """Return the path and the message of each error of a schema for a value."""
    try:
        schema(value)
    except probatio.Invalid as err:
        return [(info.path, info.message) for info in iter_validation_errors(err)]
    return []


def assert_block_schema_errors_match(
    document_schema: Callable[[Any], Any],
    block_kinds: Mapping[str, BlockKind],
    config: dict[str, Any],
) -> None:
    """Assert the schema of each block gives the errors the document schema gives.

    The errors of the document schema for a block are the ones below the key
    of the block. block_kinds has the kind of the block at each key of the
    validated config.
    """
    # The schemas change the config in place
    config = deepcopy(config)
    document_errors = _schema_errors(document_schema, config)
    for key in config.keys() & block_kinds.keys():
        assert _schema_errors(_BLOCK_SCHEMAS[block_kinds[key]], config[key]) == [
            (path[1:], message)
            for path, message in document_errors
            if path[:1] == (key,)
        ], key
