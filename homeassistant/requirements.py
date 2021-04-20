"""Module to handle installing requirements."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
import os
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.loader import Integration, IntegrationNotFound, async_get_integration
import homeassistant.util.package as pkg_util

# mypy: disallow-any-generics

DATA_PIP_LOCK = "pip_lock"
DATA_PKG_CACHE = "pkg_cache"
DATA_INTEGRATIONS_WITH_REQS = "integrations_with_reqs"
CONSTRAINT_FILE = "package_constraints.txt"
DISCOVERY_INTEGRATIONS: dict[str, Iterable[str]] = {
    "dhcp": ("dhcp",),
    "mqtt": ("mqtt",),
    "ssdp": ("ssdp",),
    "zeroconf": ("zeroconf", "homekit"),
}


class RequirementsNotFound(HomeAssistantError):
    """Raised when a component is not found."""

    def __init__(self, domain: str, requirements: list[str]) -> None:
        """Initialize a component not found error."""
        super().__init__(f"Requirements for {domain} not found: {requirements}.")
        self.domain = domain
        self.requirements = requirements


async def async_get_integration_with_requirements(
    hass: HomeAssistant, domain: str, done: set[str] | None = None
) -> Integration:
    """Get an integration with all requirements installed, including the dependencies.

    This can raise IntegrationNotFound if manifest or integration
    is invalid, RequirementNotFound if there was some type of
    failure to install requirements.
    """
    if done is None:
        done = {domain}
    else:
        done.add(domain)

    integration = await async_get_integration(hass, domain)

    if hass.config.skip_pip:
        return integration

    cache = hass.data.get(DATA_INTEGRATIONS_WITH_REQS)
    if cache is None:
        cache = hass.data[DATA_INTEGRATIONS_WITH_REQS] = {}

    int_or_evt: Integration | asyncio.Event | None | UndefinedType = cache.get(
        domain, UNDEFINED
    )

    if isinstance(int_or_evt, asyncio.Event):
        await int_or_evt.wait()
        int_or_evt = cache.get(domain, UNDEFINED)

        # When we have waited and it's UNDEFINED, it doesn't exist
        # We don't cache that it doesn't exist, or else people can't fix it
        # and then restart, because their config will never be valid.
        if int_or_evt is UNDEFINED:
            raise IntegrationNotFound(domain)

    if int_or_evt is not UNDEFINED:
        return cast(Integration, int_or_evt)

    event = cache[domain] = asyncio.Event()

    if integration.requirements:
        await async_process_requirements(
            hass, integration.domain, integration.requirements
        )

    deps_to_check = [
        dep
        for dep in integration.dependencies + integration.after_dependencies
        if dep not in done
    ]

    for check_domain, to_check in DISCOVERY_INTEGRATIONS.items():
        if (
            check_domain not in done
            and check_domain not in deps_to_check
            and any(check in integration.manifest for check in to_check)
        ):
            deps_to_check.append(check_domain)

    if deps_to_check:
        results = await asyncio.gather(
            *[
                async_get_integration_with_requirements(hass, dep, done)
                for dep in deps_to_check
            ],
            return_exceptions=True,
        )
        for result in results:
            if not isinstance(result, BaseException):
                continue
            if not isinstance(result, IntegrationNotFound) or not (
                not integration.is_built_in
                and result.domain in integration.after_dependencies
            ):
                raise result

    cache[domain] = integration
    event.set()
    return integration


async def async_process_requirements(
    hass: HomeAssistant, name: str, requirements: list[str]
) -> None:
    """Install the requirements for a component or platform.

    This method is a coroutine. It will raise RequirementsNotFound
    if an requirement can't be satisfied.
    """
    pip_lock = hass.data.get(DATA_PIP_LOCK)
    if pip_lock is None:
        pip_lock = hass.data[DATA_PIP_LOCK] = asyncio.Lock()

    kwargs = pip_kwargs(hass.config.config_dir)

    async with pip_lock:
        for req in requirements:
            if pkg_util.is_installed(req):
                continue

            def _install(req: str, kwargs: dict[str, Any]) -> bool:
                """Install requirement."""
                return pkg_util.install_package(req, **kwargs)

            ret = await hass.async_add_executor_job(_install, req, kwargs)

            if not ret:
                raise RequirementsNotFound(name, [req])


def pip_kwargs(config_dir: str | None) -> dict[str, Any]:
    """Return keyword arguments for PIP install."""
    is_docker = pkg_util.is_docker_env()
    kwargs = {
        "constraints": os.path.join(os.path.dirname(__file__), CONSTRAINT_FILE),
        "no_cache_dir": is_docker,
    }
    if "WHEELS_LINKS" in os.environ:
        kwargs["find_links"] = os.environ["WHEELS_LINKS"]
    if not (config_dir is None or pkg_util.is_virtual_env()) and not is_docker:
        kwargs["target"] = os.path.join(config_dir, "deps")
    return kwargs
