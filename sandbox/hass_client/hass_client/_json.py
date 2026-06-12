"""Shared JSON coercion for the sandbox client package.

A single source of truth for turning rich Home Assistant objects (sets, enums,
``as_dict`` objects, datetimes, …) into the plain dict/list/scalar shapes the
protobuf ``Struct`` helpers and the wire accept.

Built on Home Assistant's own :func:`json_encoder_default` so it stays in
lockstep with how the rest of HA serialises these types, with one addition: a
``str(obj)`` fallback for anything the encoder doesn't know. The sandbox
forwards integration-supplied event data and capability attributes that can
hold arbitrary domain objects; the fallback keeps a single odd field from
raising and dropping the whole best-effort payload — the tolerance the former
hand-rolled coercers (``event_mirror._to_json_safe`` / ``entity_bridge._serialise``)
provided before they drifted apart.
"""

from typing import Any

import orjson

from homeassistant.helpers.json import json_encoder_default
from homeassistant.util.json import json_loads


def _default(obj: Any) -> Any:
    """HA's JSON encoder, with a ``str(obj)`` fallback for unknown objects."""
    try:
        return json_encoder_default(obj)
    except TypeError:
        return str(obj)


def json_safe(value: Any) -> Any:
    """Return ``value`` coerced to plain JSON-safe Python objects.

    Round-trips through Home Assistant's ``as_dict``/set/enum-aware encoder
    (mirroring ``homeassistant.helpers.json.json_bytes``, plus the ``str``
    fallback) so callers get plain dict/list/scalar shapes ready for
    ``dict_to_struct`` / Struct updates.
    """
    return json_loads(
        orjson.dumps(value, option=orjson.OPT_NON_STR_KEYS, default=_default)
    )
