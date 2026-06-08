"""Async client for the A Better Routeplanner v1 API.

Wire surface for vehicle enumeration (telemetry uses the v2 SSE stream):

* ``POST https://api.iternio.com/1/session/get_tlm``
* Header ``Authorization: APIKEY <ABRP_APP_KEY>``
* Body ``{"session_id": "<oauth access_token>"}``
* Response envelope ``{"status": "ok"|"error", "result"|"error": ...}``

The v1 endpoint returns ``200 OK`` for both successful calls and most
business-level failures; auth and validation failures arrive as
``200 {"status": "error", "error": "<text>"}``. The auth-vs-generic split is
a text-matching heuristic on the error string until ABRP exposes
machine-readable error codes.
"""

from codecs import getincrementaldecoder
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass
from http import HTTPStatus
import json
import logging
import re
from typing import Any, cast

from aiohttp import ClientError, ClientSession, ClientTimeout

from ._telemetry_models import OutputPoint, OutputPointWithVehicleId
from .const import (
    ABRP_API_BASE,
    ABRP_API_V2_BASE,
    ABRP_V2_TLM_ENDPOINT,
    ENDPOINT_GET_TLM,
    HEADER_ABRP_SESSION,
    HEADER_API_KEY,
)

_LOGGER = logging.getLogger(__name__)

# Pre-headers handshake bounds for the long-lived SSE GET. ``total=None`` is
# mandatory — the stream runs for the lifetime of the connection (target ~200s
# server-close cadence per the heartbeat probe) and a total-elapsed budget
# would tear it down. ``connect`` covers DNS + TCP + TLS as a whole;
# ``sock_connect`` bounds the bare TCP handshake inside that envelope so a
# wedged DNS/TLS step still surfaces within ``sock_connect`` rather than
# waiting out the full ``connect`` budget. Detection of in-stream stall is
# handled at the coordinator layer via a wall-clock watchdog, NOT
# ``sock_read`` — see the SSE-loop docstring in coordinator.py.
_SSE_CONNECT_TIMEOUT_SECONDS = 30
_SSE_SOCK_CONNECT_TIMEOUT_SECONDS = 15

# One-shot seed GET (``/2/tlm/{vehicle_id}``) is best-effort: a hung response
# must not block ``async_setup_entry``. The SSE consumer backfills any missed
# metrics on the first frame, so 30 s is a generous upper bound that still
# bounds the seed phase.
_ONE_SHOT_TIMEOUT_SECONDS = 30

# Heuristic match against the v1 envelope ``error`` text. The keywords are
# word-bounded to avoid matching unrelated business errors that happen to
# contain a substring (e.g. "invalid vehicle_model" matches a bare "invalid").
# Compound forms like ``session_id`` / ``auth_required`` are their own
# alternatives because the ``_`` is a regex word character and would block
# the shorter ``\bsession\b`` / ``\bauth\b`` boundary match.
_AUTH_ERROR_RE = re.compile(
    r"\b(?:"
    r"session|session_id|token|expired|unauthorized"
    r"|authentication|authorization|auth_required|auth_failed"
    r"|invalid_credentials"
    r")\b",
    re.IGNORECASE,
)


class AbrpAuthError(Exception):
    """Authentication or session failure from the ABRP API."""


class AbrpApiError(Exception):
    """Non-auth ABRP API failure (transport, malformed response, business error)."""


@dataclass(frozen=True, slots=True)
class AbrpVehicle:
    """One vehicle: v1 garage enumeration enriched with v2 catalog lookup.

    Identity fields (``vehicle_id``, ``name``, ``vehicle_model``, ``paint``) come
    from ``POST /1/session/get_tlm``. The ``device_model`` and
    ``device_manufacturer`` fields are derived at coordinator-refresh time
    from a single longest-colon-token-prefix match against the v2 catalog
    (see :func:`_match_catalog_entry`), and surfaced via
    :attr:`DeviceInfo.model` / :attr:`DeviceInfo.manufacturer` on the
    per-vehicle device card. ``device_manufacturer`` carries the catalog
    make (e.g. ``"Tesla"`` / ``"Rivian"``); on catalog miss it stays
    ``None`` and the device card's Manufacturer slot falls back to the
    integration name at the sensor layer. ``device_model`` likewise stays
    ``None`` on miss and the Model slot falls back to the raw ``vehicle_model``
    typecode.

    ``name`` stays nullable defensively (some live-API records have no
    nickname).
    """

    vehicle_id: int
    name: str | None
    vehicle_model: str
    paint: str | None
    device_model: str | None = None
    device_manufacturer: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One catalog vehicle template from ``GET /2/vehicle/_list``.

    The v2 catalog endpoint returns ~1100 vehicle templates indexed by
    ``typecode``. Each entry carries nameplate metadata (maker, model, title,
    year window, battery capacity) that the v1 garage endpoint does not
    expose. Optional fields normalise via :func:`_str_or_none` /
    :func:`_int_or_none` so empty strings and wrong types collapse to
    ``None`` at the parse boundary instead of poisoning downstream gates.
    """

    typecode: str
    manufacturer: str | None
    model: str | None
    title: str | None
    start_year: int | None
    end_year: int | None
    battery_capacity_wh: int | None


class AbrpClient:
    """Hand-written async client for the ABRP v1 garage + v2 catalog APIs."""

    def __init__(
        self,
        websession: ClientSession,
        partner_key: str,
        access_token: str,
    ) -> None:
        """Initialize the client.

        ``partner_key`` is the static ABRP app key (used in v1's
        ``Authorization: APIKEY <key>`` header and in v2's ``X-API-KEY``
        header). ``access_token`` is the OAuth2 access_token issued by the
        ABRP OIDC provider — the v1 endpoint accepts it in the request body
        as ``session_id``; the v2 catalog endpoint expects it in
        ``X-ABRP-SESSION``.
        """
        self._websession = websession
        self._partner_key = partner_key
        self._access_token = access_token

    async def async_get_vehicles(self) -> list[AbrpVehicle]:
        """Return the authenticated user's garage.

        Raises:
            AbrpAuthError: HTTP 401/403, or 200 envelope with auth-flavoured
                ``error`` text.
            AbrpApiError: any other HTTP/transport/parse failure, or 200
                envelope with non-auth ``error`` text.
        """
        url = f"{ABRP_API_BASE}/{ENDPOINT_GET_TLM}"
        headers = {"Authorization": f"APIKEY {self._partner_key}"}
        body = {"session_id": self._access_token}
        try:
            async with self._websession.post(
                url, headers=headers, json=body
            ) as response:
                if response.status in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                ):
                    raise AbrpAuthError(f"HTTP {response.status}")
                # 401/403 only; other 4xx → AbrpApiError. Revisit if ABRP
                # starts returning auth-flavoured 4xx with structured bodies
                # (current v1 surfaces auth failures as 200 + status:"error").
                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise AbrpApiError(f"HTTP {response.status}")
                try:
                    payload: dict[str, Any] = await response.json()
                except ValueError as err:
                    raise AbrpApiError(
                        f"malformed JSON in garage response: {err}"
                    ) from err
        except ClientError as err:
            raise AbrpApiError(str(err)) from err

        if not isinstance(payload, dict):
            raise AbrpApiError(
                f"unexpected garage payload shape: {type(payload).__name__}"
            )
        if payload.get("status") != "ok":
            error_text = str(payload.get("error", "unknown"))
            if _AUTH_ERROR_RE.search(error_text):
                raise AbrpAuthError(error_text)
            raise AbrpApiError(error_text)

        records = payload.get("result")
        if not isinstance(records, list):
            raise AbrpApiError("missing or malformed 'result' in success response")
        return [_parse_vehicle(record) for record in records]

    async def async_get_catalog(self) -> dict[str, CatalogEntry]:
        """Fetch the v2 vehicle catalog from ``GET /2/vehicle/_list``.

        Returns a dict keyed by typecode for O(1) lookup. The catalog is
        ~850 KB (~1100 entries, no pagination) and stable
        enough that fetching once per coordinator lifetime is appropriate;
        reload of the config entry is the only refresh path. Mid-session
        catalog updates on ABRP's side do not materialise new sensors until
        reload — explicitly documented for users in the integration docs.

        Auth: dual-header (``X-API-KEY`` partner key + ``X-ABRP-SESSION``
        OAuth access_token), same shape as the SSE telemetry client and
        probe-confirmed on the catalog endpoint.

        Raises:
            AbrpAuthError: HTTP 401/403 (session rejected by ABRP).
            AbrpApiError: any other 4xx/5xx HTTP, transport, or parse
                failure. The coordinator treats this as non-fatal and
                degrades to an empty catalog for the rest of the session.
        """
        url = f"{ABRP_API_V2_BASE}/vehicle/_list"
        headers = {
            "Accept": "application/json",
            HEADER_API_KEY: self._partner_key,
            HEADER_ABRP_SESSION: self._access_token,
        }
        try:
            async with self._websession.get(
                url,
                headers=headers,
                timeout=ClientTimeout(total=_ONE_SHOT_TIMEOUT_SECONDS),
            ) as response:
                if response.status in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                ):
                    raise AbrpAuthError(f"HTTP {response.status}")
                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise AbrpApiError(f"HTTP {response.status}")
                try:
                    payload = await response.json()
                except ValueError as err:
                    raise AbrpApiError(
                        f"malformed JSON in catalog response: {err}"
                    ) from err
        except (ClientError, TimeoutError) as err:
            # A bare ``ClientTimeout(total=...)`` raises naked
            # ``asyncio.TimeoutError`` which is NOT a ``ClientError`` subclass,
            # so the catch band must name it explicitly. Wrapping at the client
            # boundary keeps the coordinator's ``(AbrpAuthError, AbrpApiError)``
            # fail-soft path engaged when the catalog endpoint hangs past the
            # budget.
            raise AbrpApiError(str(err)) from err

        if not isinstance(payload, dict):
            raise AbrpApiError(
                f"unexpected catalog payload shape: {type(payload).__name__}"
            )
        vehicles_raw = payload.get("vehicles")
        if not isinstance(vehicles_raw, list):
            raise AbrpApiError("missing or malformed 'vehicles' in catalog response")
        catalog: dict[str, CatalogEntry] = {}
        for record in vehicles_raw:
            if not isinstance(record, dict):
                continue
            entry = _parse_catalog_entry(record)
            if entry is not None:
                catalog[entry.typecode] = entry
        return catalog


class AbrpTelemetryClient:
    """SSE consumer for the v2 ``/2/tlm`` multi-vehicle telemetry stream.

    Probe-confirmed wire format: ``X-API-KEY`` (partner key) +
    ``X-ABRP-SESSION`` (OAuth ``access_token``), ``Accept: text/event-stream``.
    Server sends standard SSE — ``data: <json>`` frames separated by blank
    lines, ``:`` comment lines for keepalive. Frames are **partial-update
    deltas**: a ``power``-only frame must not overwrite a previously-seen
    ``soc``; that merge happens at the coordinator, not here.
    """

    def __init__(
        self,
        websession: ClientSession,
        partner_key: str,
        session_token: str,
    ) -> None:
        """Initialize the client.

        ``partner_key`` is the static ABRP app key; ``session_token`` is the
        per-user OAuth ``access_token`` (same one the v1 client uses as
        ``session_id`` in its request body).
        """
        self._websession = websession
        self._partner_key = partner_key
        self._session_token = session_token

    async def async_get_one_shot(self, vehicle_id: int) -> OutputPoint:
        """Fetch the current telemetry snapshot for one vehicle.

        ``GET /2/tlm/{vehicle_id}`` with ``Accept: application/json`` returns
        the bare :class:`OutputPoint` (the single-vehicle endpoint scopes
        ``vehicleId`` via the path). The seed path is best-effort: an empty
        response body ``{}`` is a valid "no metric data yet" answer; the
        coordinator's ``apply_frame`` does the null-filter + deep-merge on
        top of whatever shape arrives here.

        Raises:
            AbrpAuthError: HTTP 401/403 (session rejected by ABRP).
            AbrpApiError: any other 4xx/5xx HTTP or transport failure.
        """
        url = f"{ABRP_API_V2_BASE}/{ABRP_V2_TLM_ENDPOINT}/{vehicle_id}"
        headers = {
            "Accept": "application/json",
            HEADER_API_KEY: self._partner_key,
            HEADER_ABRP_SESSION: self._session_token,
        }
        try:
            async with self._websession.get(
                url,
                headers=headers,
                timeout=ClientTimeout(total=_ONE_SHOT_TIMEOUT_SECONDS),
            ) as response:
                if response.status in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                ):
                    raise AbrpAuthError(f"HTTP {response.status}")
                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise AbrpApiError(f"HTTP {response.status}")
                try:
                    payload = await response.json()
                except ValueError as err:
                    raise AbrpApiError(
                        f"malformed JSON in one-shot response: {err}"
                    ) from err
        except ClientError as err:
            raise AbrpApiError(str(err)) from err
        if not isinstance(payload, dict):
            raise AbrpApiError(
                f"unexpected one-shot payload shape: {type(payload).__name__}"
            )
        return cast(OutputPoint, payload)

    async def stream(
        self, vehicle_ids: list[int]
    ) -> AsyncGenerator[OutputPointWithVehicleId]:
        """Open the SSE stream and yield parsed frames.

        Raises:
            AbrpAuthError: HTTP 401/403 (session rejected by ABRP).
            AbrpApiError: any other transport/parse failure. Callers treat
                this as a transient disconnect and reconnect with backoff.
        """
        url = f"{ABRP_API_V2_BASE}/{ABRP_V2_TLM_ENDPOINT}"
        params = {"vehicleIds": ",".join(str(v) for v in vehicle_ids)}
        headers = {
            "Accept": "text/event-stream",
            HEADER_API_KEY: self._partner_key,
            HEADER_ABRP_SESSION: self._session_token,
        }
        try:
            async with self._websession.get(
                url,
                params=params,
                headers=headers,
                timeout=ClientTimeout(
                    total=None,
                    connect=_SSE_CONNECT_TIMEOUT_SECONDS,
                    sock_connect=_SSE_SOCK_CONNECT_TIMEOUT_SECONDS,
                ),
            ) as response:
                if response.status in (
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.FORBIDDEN,
                ):
                    raise AbrpAuthError(f"HTTP {response.status}")
                if response.status >= HTTPStatus.BAD_REQUEST:
                    raise AbrpApiError(f"HTTP {response.status}")

                # Incremental UTF-8 decoder preserves multi-byte sequences
                # that span chunk boundaries — naive per-chunk decode would
                # mojibake on Unicode vehicle names / location strings and
                # the JSON parser would then reject the otherwise-valid
                # frame.
                decoder = getincrementaldecoder("utf-8")(errors="replace")
                buffer = ""
                async for chunk in response.content.iter_any():
                    buffer += decoder.decode(chunk)
                    # SSE spec accepts ``\n``, ``\r\n`` and ``\r`` as line
                    # terminators. Normalize before splitting on ``\n\n``.
                    # A trailing lone ``\r`` may be the first half of a
                    # ``\r\n`` pair that arrives in the next chunk — hold
                    # it back so the pair-rewrite below sees the whole
                    # sequence and we don't mistake a CR for an extra
                    # blank line.
                    if buffer.endswith("\r"):
                        buffer, held_cr = buffer[:-1], "\r"
                    else:
                        held_cr = ""
                    buffer = buffer.replace("\r\n", "\n").replace("\r", "\n")
                    buffer += held_cr
                    while "\n\n" in buffer:
                        event, _, buffer = buffer.partition("\n\n")
                        frame = _parse_sse_event(event)
                        if frame is not None:
                            yield frame
                # Flush the incremental decoder and any residual buffer in
                # case the server closed the stream gracefully without a
                # trailing blank line. Rare but observed on cold reconnects.
                buffer += decoder.decode(b"", final=True)
                buffer = buffer.replace("\r\n", "\n").replace("\r", "\n")
                if buffer.strip():
                    frame = _parse_sse_event(buffer)
                    if frame is not None:
                        yield frame
        except ClientError as err:
            raise AbrpApiError(str(err)) from err


def _parse_sse_event(event: str) -> OutputPointWithVehicleId | None:
    r"""Parse one ``\n\n``-terminated SSE event block into a JSON dict.

    Returns ``None`` for events that carry only comments / keepalives, or
    for frames missing the required ``vehicleId`` key (probable upstream
    drift — drop quietly with a debug log rather than killing the SSE
    consumer task). Raises :exc:`AbrpApiError` on malformed JSON.
    """
    data_parts: list[str] = []
    for line in event.split("\n"):
        if not line or line.startswith(":"):
            # blank line (intra-event whitespace) or SSE comment (``: heartbeat``)
            continue
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
    if not data_parts:
        return None
    payload = "\n".join(data_parts)
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as err:
        raise AbrpApiError(f"malformed SSE frame: {err}") from err
    if not isinstance(decoded, dict) or "vehicleId" not in decoded:
        _LOGGER.debug("Dropping SSE frame missing 'vehicleId': %r", decoded)
        return None
    # Per-metric shape validation lives at the consumer (``value_fn``) which
    # tolerates missing/null keys.
    return cast(OutputPointWithVehicleId, decoded)


def _parse_vehicle(record: dict[str, Any]) -> AbrpVehicle:
    """Parse one ``result`` array entry into an ``AbrpVehicle``.

    Constructs the dataclass with the v1 identity fields populated and the
    catalog-enrichment fields defaulted to ``None``. Enrichment happens later
    in the coordinator via :func:`_enrich_with_catalog` once the v2 catalog
    is loaded.
    """
    try:
        name = record.get("name")
        return AbrpVehicle(
            vehicle_id=int(record["vehicle_id"]),
            name=str(name) if name is not None else None,
            vehicle_model=str(record["car_model"]),
            paint=record.get("paint"),
        )
    except (KeyError, TypeError, ValueError) as err:
        raise AbrpApiError(f"malformed vehicle record: {err}") from err


def _str_or_none(value: Any) -> str | None:
    """Normalise an optional catalog string field.

    Non-strings collapse to ``None``. Strings are stripped at the parse
    boundary; the result is ``None`` if nothing remains, otherwise the
    trimmed token. Empty (``""``) and whitespace-only (``"   "``) inputs
    therefore both collapse to ``None``, and whitespace-padded inputs
    (``"  Rivian  "``) are normalised once at parse time rather than
    leaking padding into every downstream consumer.

    Load-bearing consumer: :func:`_compute_device_model` uses
    ``entry.manufacturer and entry.model`` as a truthy filter — any
    string that survives this helper must be presentable verbatim in
    the composed ``DeviceInfo.model`` display. Single-site
    normalisation guarantees the filter, the composition formula's
    ``f"{best.manufacturer} {best.model}"`` interpolation, and the
    title-append step all see the same trimmed shape, so the display
    string never carries upstream padding artefacts.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _int_or_none(value: Any) -> int | None:
    """Normalise an optional catalog int field.

    Accepts ``int`` strictly: ``bool`` is rejected up front because
    ``bool ⊂ int`` in Python (``isinstance(True, int) is True``), and
    silently coercing ``True → 1`` for ``startYear`` / ``endYear`` /
    ``batteryCapacityWh`` would surface a nonsense value on the sensor.
    Floats, strings-that-look-like-ints, and other types also collapse to
    ``None`` so upstream type drift fails loudly (sensor reads as
    ``unknown``) rather than masquerading as a real value.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _parse_catalog_entry(record: Mapping[str, Any]) -> CatalogEntry | None:
    """Parse one ``vehicles[i]`` wire record into a :class:`CatalogEntry`.

    Returns ``None`` when the record's ``typecode`` is missing, empty, or
    non-string — those entries can't participate in the typecode-keyed
    dict that :meth:`AbrpClient.async_get_catalog` builds. Per-field
    typing on the optional columns runs through :func:`_str_or_none` /
    :func:`_int_or_none` so empty strings, ``null``s, and wrong types all
    collapse cleanly to ``None``.
    """
    typecode = record.get("typecode")
    if not isinstance(typecode, str) or not typecode:
        return None
    return CatalogEntry(
        typecode=typecode,
        manufacturer=_str_or_none(record.get("manufacturer")),
        model=_str_or_none(record.get("model")),
        title=_str_or_none(record.get("title")),
        start_year=_int_or_none(record.get("startYear")),
        end_year=_int_or_none(record.get("endYear")),
        battery_capacity_wh=_int_or_none(record.get("batteryCapacityWh")),
    )


def _typecode_prefix_match(candidate: str, target: str) -> bool:
    """True if ``candidate`` is a colon-token ancestor of ``target``.

    Either exact equality, or ``target`` starts with ``candidate + ":"`` —
    so ``rivian:r1s`` matches ``rivian:r1s:25:...`` but ``rivian:r1`` does
    NOT match ``rivian:r1s:...``. Token-boundary discipline matches ABRP's
    hierarchical typecode convention (``manufacturer:model:year:battery:
    drivetrain:...``) so a future short-ancestor catalog row doesn't
    cross-match a longer descendant from an unrelated lineage.
    """
    return candidate == target or target.startswith(candidate + ":")


def _match_catalog_entry(
    typecode: str, catalog: Mapping[str, CatalogEntry]
) -> CatalogEntry | None:
    """Select the longest-prefix catalog entry usable for device-card display.

    Picks the entry whose ``typecode`` is the longest colon-token ancestor
    of ``typecode`` AND whose ``manufacturer`` + ``model`` columns are
    non-None (a malformed longest match must not shadow a usable shorter
    one). Returns ``None`` when nothing matches.

    Equal-length ties are provably impossible: two distinct strings A and B
    of equal length n that both prefix-match target T would both equal T[:n],
    so A == T[:n] == B → A == B, contradicting distinctness. No tie-break
    code path is needed.
    """
    candidates = [
        entry
        for entry in catalog.values()
        if entry.manufacturer
        and entry.model
        and _typecode_prefix_match(entry.typecode, typecode)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: len(entry.typecode))


def _compose_device_model(best: CatalogEntry) -> str:
    """Build the :attr:`DeviceInfo.model` display string from a catalog entry.

    Build formula:

        "{manufacturer} {model}" + optional " {startYear-endYear or startYear}"
                                  + optional " {title}"

    The year segment is dropped when ``start_year`` is missing (covers both
    "no start_year" and "end_year-only"). The title segment is appended
    stripped: under normal wire flow :func:`_str_or_none` has already
    normalised the input at parse time, but the use-site ``strip()``
    keeps the helper robust against any directly-constructed
    :class:`CatalogEntry` that happens to carry padded text.
    """
    parts = [f"{best.manufacturer} {best.model}"]
    if best.start_year is not None and best.end_year is not None:
        parts.append(f"{best.start_year}-{best.end_year}")
    elif best.start_year is not None:
        parts.append(str(best.start_year))
    if best.title and (title := best.title.strip()):
        parts.append(title)
    return " ".join(parts)


def _compute_device_model(
    typecode: str, catalog: Mapping[str, CatalogEntry]
) -> str | None:
    """Compose the display string for :attr:`DeviceInfo.model` from the v2 catalog.

    Thin wrapper retained for the parametrized regression test; delegates to
    :func:`_match_catalog_entry` + :func:`_compose_device_model`. Returns
    ``None`` when nothing matches — the caller then falls back to the raw
    typecode at the device-info layer.
    """
    best = _match_catalog_entry(typecode, catalog)
    return _compose_device_model(best) if best is not None else None


def _enrich_with_catalog(
    raw: AbrpVehicle, catalog: Mapping[str, CatalogEntry]
) -> AbrpVehicle:
    """Join one v1 vehicle record with the v2 catalog (skip-on-miss).

    Catalog hit: produce a new :class:`AbrpVehicle` carrying the v1 identity
    fields plus the composed ``device_model`` and the catalog
    ``device_manufacturer``. Catalog miss: both stay ``None`` and the device
    card falls back to the raw ``vehicle_model`` typecode (Model) and the
    integration name (Manufacturer) at the sensor layer.

    No typecode-string parsing fallback. Skip-on-miss beats best-effort
    synthesis — a derived "RIVIAN" from a raw typecode reads worse than
    ``unknown``, and renders better once ABRP catalogs the vehicle on the
    next coordinator reload.
    """
    best = _match_catalog_entry(raw.vehicle_model, catalog)
    if best is None:
        return raw
    return AbrpVehicle(
        vehicle_id=raw.vehicle_id,
        name=raw.name,
        vehicle_model=raw.vehicle_model,
        paint=raw.paint,
        device_model=_compose_device_model(best),
        device_manufacturer=best.manufacturer,
    )
