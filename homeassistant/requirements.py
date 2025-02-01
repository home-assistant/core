"""Module to handle installing requirements."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import contextlib
import logging
import os
from typing import Any

from packaging.requirements import Requirement

from .core import HomeAssistant, callback
from .exceptions import HomeAssistantError
from .helpers import singleton
from .loader import Integration, IntegrationNotFound, async_get_integration
from .util import package as pkg_util

# The default is too low when the internet connection is satellite or high latency
PIP_TIMEOUT = 60
MAX_INSTALL_FAILURES = 3
DATA_REQUIREMENTS_MANAGER = "requirements_manager"
CONSTRAINT_FILE = "package_constraints.txt"
DISCOVERY_INTEGRATIONS: dict[str, Iterable[str]] = {
    "dhcp": ("dhcp",),
    "mqtt": ("mqtt",),
    "ssdp": ("ssdp",),
    "zeroconf": ("zeroconf", "homekit"),
}
_LOGGER = logging.getLogger(__name__)


class RequirementsNotFound(HomeAssistantError):
    """Raised when a component is not found."""

    def __init__(self, domain: str, requirements: list[str]) -> None:
        """Initialize a component not found error."""
        super().__init__(f"Requirements for {domain} not found: {requirements}.")
        self.domain = domain
        self.requirements = requirements


async def async_get_integration_with_requirements(
    hass: HomeAssistant, domain: str
) -> Integration:
    """Get an integration with all requirements installed, including the dependencies.

    This can raise IntegrationNotFound if manifest or integration
    is invalid, RequirementNotFound if there was some type of
    failure to install requirements.
    """
    manager = _async_get_manager(hass)
    return await manager.async_get_integration_with_requirements(domain)


async def async_process_requirements(
    hass: HomeAssistant, name: str, requirements: list[str]
) -> None:
    """Install the requirements for a component or platform.

    This method is a coroutine. It will raise RequirementsNotFound
    if an requirement can't be satisfied.
    """
    await _async_get_manager(hass).async_process_requirements(name, requirements)


async def async_load_installed_versions(
    hass: HomeAssistant, requirements: set[str]
) -> None:
    """Load the installed version of requirements."""
    await _async_get_manager(hass).async_load_installed_versions(requirements)


@callback
@singleton.singleton(DATA_REQUIREMENTS_MANAGER)
def _async_get_manager(hass: HomeAssistant) -> RequirementsManager:
    """Get the requirements manager."""
    return RequirementsManager(hass)


@callback
def async_clear_install_history(hass: HomeAssistant) -> None:
    """Forget the install history."""
    _async_get_manager(hass).install_failure_history.clear()


def pip_kwargs(config_dir: str | None) -> dict[str, Any]:
    """Return keyword arguments for PIP install."""
    is_docker = pkg_util.is_docker_env()
    kwargs = {
        "constraints": os.path.join(os.path.dirname(__file__), CONSTRAINT_FILE),
        "timeout": PIP_TIMEOUT,
    }
    if not (config_dir is None or pkg_util.is_virtual_env()) and not is_docker:
        kwargs["target"] = os.path.join(config_dir, "deps")
    return kwargs


def _install_with_retry(requirement: str, kwargs: dict[str, Any]) -> bool:
    """Try to install a package up to MAX_INSTALL_FAILURES times."""
    for _ in range(MAX_INSTALL_FAILURES):
        if pkg_util.install_package(requirement, **kwargs):
            return True
    return False


def _install_requirements_if_missing(
    requirements: list[str], kwargs: dict[str, Any]
) -> tuple[set[str], set[str]]:
    """Install requirements if missing."""
    installed: set[str] = set()
    failures: set[str] = set()
    for req in requirements:
        if pkg_util.is_installed(req) or _install_with_retry(req, kwargs):
            installed.add(req)
            continue
        failures.add(req)
    return installed, failures


class RequirementsManager:
    """Manage requirements."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the requirements manager."""
        self.hass = hass
        self.pip_lock = asyncio.Lock()
        self.integrations_with_reqs: dict[
            str, Integration | asyncio.Future[Integration]
        ] = {}
        self.install_failure_history: set[str] = set()
        self.is_installed_cache: set[str] = set()

    async def async_get_integration_with_requirements(
        self, domain: str, done: set[str] | None = None
    ) -> Integration:
        """Get an integration with all requirements installed, including dependencies.

        This can raise IntegrationNotFound if manifest or integration
        is invalid, RequirementNotFound if there was some type of
        failure to install requirements.
        """
        if done is None:
            done = {domain}
        else:
            done.add(domain)

        cache = self.integrations_with_reqs
        if int_or_fut := cache.get(domain):
            if isinstance(int_or_fut, Integration):
                return int_or_fut
            return await int_or_fut

        future = cache[domain] = self.hass.loop.create_future()
        try:
            integration = await async_get_integration(self.hass, domain)
            if not self.hass.config.skip_pip:
                await self._async_process_integration(integration, done)
        except BaseException as ex:
            # We do not cache failures as we want to retry, or
            # else people can't fix it and then restart, because
            # their config will never be valid.
            del cache[domain]
            future.set_exception(ex)
            with contextlib.suppress(BaseException):
                # Clear the flag as its normal that nothing
                # will wait for this future to be resolved
                # if there are no concurrent requirements fetches.
                await future
            raise

        cache[domain] = integration
        future.set_result(integration)
        return integration

    async def _async_process_integration(
        self, integration: Integration, done: set[str]
    ) -> None:
        """Process an integration and requirements."""
        if integration.requirements:
            await self.async_process_requirements(
                integration.domain, integration.requirements
            )

        cache = self.integrations_with_reqs

        deps_to_check = {
            dep
            for dep in integration.dependencies + integration.after_dependencies
            if dep not in done
            # If the dep is in the cache and it's an Integration
            # it's already been checked for the requirements and we should
            # not check it again.
            and (
                not (cached_integration := cache.get(dep))
                or type(cached_integration) is not Integration
            )
        }

        for check_domain, to_check in DISCOVERY_INTEGRATIONS.items():
            if (
                check_domain not in done
                and check_domain not in deps_to_check
                # If the integration is in the cache and it's an Integration
                # it's already been checked for the requirements and we should
                # not check it again.
                and (
                    not (cached_integration := cache.get(check_domain))
                    or type(cached_integration) is not Integration
                )
                and any(check in integration.manifest for check in to_check)
            ):
                deps_to_check.add(check_domain)

        if not deps_to_check:
            return

        exceptions: list[Exception] = []
        # We don't create tasks here since everything waits for the pip lock
        # anyways and we want to make sure we don't start a bunch of tasks
        # that will just wait for the lock.
        for dep in deps_to_check:
            # We want all the async_get_integration_with_requirements calls to
            # happen even if one fails. So we catch the exception and store it
            # to raise the first one after all are done to behave like asyncio
            # gather.
            try:
                await self.async_get_integration_with_requirements(dep, done)
            except IntegrationNotFound as ex:
                if (
                    integration.is_built_in
                    or ex.domain not in integration.after_dependencies
                ):
                    exceptions.append(ex)
            except Exception as ex:  # noqa: BLE001
                exceptions.insert(0, ex)

        if exceptions:
            raise exceptions[0]

    async def async_process_requirements(
        self, name: str, requirements: list[str]
    ) -> None:
        """Install the requirements for a component or platform.

        This method is a coroutine. It will raise RequirementsNotFound
        if an requirement can't be satisfied.
        """
        if self.hass.config.skip_pip_packages:
            skipped_requirements = {
                req
                for req in requirements
                if Requirement(req).name in self.hass.config.skip_pip_packages
            }

            for req in skipped_requirements:
                _LOGGER.warning("Skipping requirement %s. This may cause issues", req)

            requirements = [r for r in requirements if r not in skipped_requirements]

        if not (missing := self._find_missing_requirements(requirements)):
            return
        self._raise_for_failed_requirements(name, missing)

        async with self.pip_lock:
            # Recalculate missing again now that we have the lock
            if missing := self._find_missing_requirements(requirements):
                await self._async_process_requirements(name, missing)

    def _find_missing_requirements(self, requirements: list[str]) -> list[str]:
        """Find requirements that are missing in the cache."""
        return [req for req in requirements if req not in self.is_installed_cache]

    def _raise_for_failed_requirements(
        self, integration: str, missing: list[str]
    ) -> None:
        """Raise for failed installing integration requirements.

        Raise RequirementsNotFound so we do not keep trying requirements
        that have already failed.
        """
        for req in missing:
            if req in self.install_failure_history:
                _LOGGER.info(
                    (
                        "Multiple attempts to install %s failed, install will be"
                        " retried after next configuration check or restart"
                    ),
                    req,
                )
                raise RequirementsNotFound(integration, [req])

    async def _async_process_requirements(
        self,
        name: str,
        requirements: list[str],
    ) -> None:
        """Install a requirement and save failures."""
        kwargs = pip_kwargs(self.hass.config.config_dir)
        installed, failures = await self.hass.async_add_executor_job(
            _install_requirements_if_missing, requirements, kwargs
        )
        self.is_installed_cache |= installed
        self.install_failure_history |= failures
        if failures:
            raise RequirementsNotFound(name, list(failures))

    async def async_load_installed_versions(
        self,
        requirements: set[str],
    ) -> None:
        """Load the installed version of requirements."""
        if not (requirements_to_check := requirements - self.is_installed_cache):
            return

        self.is_installed_cache |= await self.hass.async_add_executor_job(
            pkg_util.get_installed_versions, requirements_to_check
        )
