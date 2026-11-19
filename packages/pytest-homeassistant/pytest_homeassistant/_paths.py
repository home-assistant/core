"""Paths for test fixtures and the default Home Assistant configuration."""

from pathlib import Path

import pytest

TESTS_DIR = Path.cwd() / "tests"
CONFIG_DIR: Path | None = None


def configure(config: pytest.Config) -> None:
    """Resolve test paths relative to the consuming project's configuration."""
    global TESTS_DIR, CONFIG_DIR  # noqa: PLW0603  # pylint: disable=global-statement
    TESTS_DIR = config.rootpath / config.getini("ha_test_root")
    CONFIG_DIR = (
        config.rootpath / config_dir
        if (config_dir := config.getini("ha_test_config_dir"))
        else None
    )
