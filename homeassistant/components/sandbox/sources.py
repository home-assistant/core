"""Main-side integration-source resolution for stateless sandboxes."""

from collections.abc import Callable
import logging
from typing import TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from ._proto import sandbox_pb2 as pb

_LOGGER = logging.getLogger(__name__)


class IntegrationSourceDict(TypedDict, total=False):
    """The dict shape a resolver returns for a custom (git) integration."""

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
    """Register a resolver mapping a custom domain to its git source."""
    resolvers = hass.data.setdefault(DATA_SOURCE_RESOLVERS, [])
    resolvers.append(resolver)

    @callback
    def _unregister() -> None:
        resolvers.remove(resolver)

    return _unregister


async def async_resolve_integration_source(
    hass: HomeAssistant, domain: str
) -> pb.IntegrationSource:
    """Resolve the source descriptor for ``domain``'s code."""
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
    """Build a typed git ``IntegrationSource`` from a resolver's dict."""
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
