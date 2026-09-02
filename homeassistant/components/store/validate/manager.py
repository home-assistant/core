"""Hacs validation manager."""

from __future__ import annotations

import asyncio
from importlib import import_module
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..base import HacsBase
    from ..repositories.base import HacsRepository
    from .base import ActionValidationBase


class ValidationManager:
    """Hacs validation manager."""

    def __init__(self, hacs: HacsBase, hass: HomeAssistant) -> None:
        """Initialize the setup manager class."""
        self.hacs = hacs
        self.hass = hass
        self._validators: dict[str, ActionValidationBase] = {}

    @property
    def validators(self) -> list[ActionValidationBase]:
        """Return all list of all tasks."""
        return list(self._validators.values())

    async def async_load(self, repository: HacsRepository) -> None:
        """Load all tasks."""
        self._validators = {}
        validator_files = Path(__file__).parent
        validator_modules = (
            module.stem
            for module in validator_files.glob("*.py")
            if module.name not in ("base.py", "__init__.py", "manager.py")
        )

        async def _load_module(module: str) -> None:
            task_module = import_module(f"{__package__}.{module}")
            if task := await task_module.async_setup_validator(repository=repository):
                self._validators[task.slug] = task

        await asyncio.gather(*[_load_module(task) for task in validator_modules])

    async def async_run_repository_checks(self, repository: HacsRepository) -> None:
        """Run all validators for a repository."""
        if not self.hacs.system.action:
            return

        await self.async_load(repository)

        is_pull_from_fork = (
            not os.getenv("INPUT_REPOSITORY")
            and os.getenv("GITHUB_REPOSITORY") != repository.data.full_name
        )

        validators = [
            validator
            for validator in self.validators or []
            if (
                (not validator.categories or repository.data.category in validator.categories)
                and validator.slug not in os.getenv("INPUT_IGNORE", "").split(" ")
                and (not is_pull_from_fork or validator.allow_fork)
            )
        ]

        await asyncio.gather(*[validator.execute_validation() for validator in validators])

        total = len(validators)
        failed = len([x for x in validators if x.failed])

        if failed != 0:
            repository.logger.error("%s %s/%s checks failed", repository.string, failed, total)
            exit(1)
        else:
            repository.logger.info("%s All (%s) checks passed", repository.string, total)
