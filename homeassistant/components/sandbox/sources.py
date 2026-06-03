"""Main-side integration-source resolution for stateless sandboxes.

A sandbox holds no persistent state. The last stateful bit was the
integration *code*: built-ins ride the bundled ``homeassistant`` package, but
custom (HACS) integrations live under ``<config>/custom_components`` on the
main install and are absent from a fresh sandbox. This module lets main tell
the sandbox *where to fetch the code* on ``entry_setup``; the sandbox fetches
it before setup (see ``hass_client.sources``).

Core stays HACS-agnostic via a registered-resolver hook (decision (c),
2026-06-03): HACS — or any other distribution mechanism — registers a
resolver mapping a custom domain to a git source. Core ships only the
builtin-vs-git decision; with no resolver registered the default is
builtin-only, and a custom domain raises rather than silently falling back.

Security / tag→sha contract: the ``ref`` that crosses the wire must be an
exact commit sha, never a moving tag. Core performs **no network I/O** here,
so the resolver is responsible for pinning the installed version to a sha and
returning it in ``ref`` (HACS already knows the sha of what the user
installed). ``tag`` is informational only (logs). If a resolver returns a git
source without a ``ref``, that is an error — main refuses to ship a sandbox a
moving reference.
"""

from collections.abc import Callable
import logging
from typing import TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from ._proto import sandbox_pb2 as pb

_LOGGER = logging.getLogger(__name__)


class IntegrationSourceDict(TypedDict, total=False):
    """The dict shape a resolver returns for a custom (git) integration.

    ``kind`` is always ``"git"`` (built-ins never reach a resolver). ``url``
    and ``ref`` (an exact commit sha) are required; ``domain`` and ``subdir``
    default from the domain being resolved when omitted.
    """

    kind: str
    url: str
    ref: str
    tag: str
    domain: str
    subdir: str


# A resolver maps a custom integration domain to its git source, or ``None``
# if it does not know that domain. Called only for non-built-in integrations.
SandboxSourceResolver = Callable[[str], IntegrationSourceDict | None]

DATA_SOURCE_RESOLVERS: HassKey[list[SandboxSourceResolver]] = HassKey(
    "sandbox_source_resolvers"
)


class SandboxSourceError(Exception):
    """Raised when an integration's source cannot be resolved."""


@callback
def async_register_sandbox_source_resolver(
    hass: HomeAssistant, resolver: SandboxSourceResolver
) -> Callable[[], None]:
    """Register a resolver mapping a custom domain to its git source.

    HACS (or any custom-integration distribution mechanism) calls this to
    teach the sandbox where to fetch code from. Resolvers are consulted in
    registration order; the first to return a non-``None`` source wins. The
    resolver MUST pin ``ref`` to an exact commit sha (see module docstring).

    Returns a callback that unregisters the resolver.
    """
    resolvers = hass.data.setdefault(DATA_SOURCE_RESOLVERS, [])
    resolvers.append(resolver)

    @callback
    def _unregister() -> None:
        resolvers.remove(resolver)

    return _unregister


async def async_resolve_integration_source(
    hass: HomeAssistant, domain: str
) -> pb.IntegrationSource:
    """Resolve the source descriptor for ``domain``'s code.

    Built-in integrations short-circuit to ``{kind: "builtin"}`` (the bundled
    ``homeassistant`` package provides them). For a custom integration the
    registered resolvers are consulted in order; the first git source returned
    is used. If no resolver knows the domain, raises :class:`SandboxSourceError`
    — a custom integration with no source cannot run in a stateless sandbox, so
    the failure is surfaced rather than masked.
    """
    integration = await async_get_integration(hass, domain)
    if integration.is_built_in:
        return pb.IntegrationSource(kind="builtin")

    for resolver in hass.data.get(DATA_SOURCE_RESOLVERS, []):
        source = resolver(domain)
        if source is not None:
            return _git_source_from_dict(domain, source)

    raise SandboxSourceError(
        f"no sandbox source resolver knows custom integration {domain!r}; "
        "a custom integration cannot run in a stateless sandbox without one"
    )


def _git_source_from_dict(
    domain: str, source: IntegrationSourceDict
) -> pb.IntegrationSource:
    """Build a typed git ``IntegrationSource`` from a resolver's dict.

    Validates the tag→sha pinning contract: ``url`` and an exact-sha ``ref``
    are required. ``domain`` and ``subdir`` default from ``domain``.
    """
    url = source.get("url")
    if not url:
        raise SandboxSourceError(
            f"resolver returned a git source for {domain!r} without a url"
        )
    ref = source.get("ref")
    if not ref:
        raise SandboxSourceError(
            f"resolver returned a git source for {domain!r} without a ref; "
            "the resolver must pin the version to an exact commit sha"
        )
    return pb.IntegrationSource(
        kind="git",
        url=url,
        ref=ref,
        tag=source.get("tag", ""),
        domain=source.get("domain", domain),
        subdir=source.get("subdir", f"custom_components/{domain}"),
    )


__all__ = [
    "IntegrationSourceDict",
    "SandboxSourceError",
    "SandboxSourceResolver",
    "async_register_sandbox_source_resolver",
    "async_resolve_integration_source",
]
