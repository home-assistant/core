"""Pytest configuration for benchmarks."""

import pytest


def pytest_configure(config):
    """Configure pytest for benchmarking."""
    config.addinivalue_line(
        "markers",
        "benchmark: mark test as a performance benchmark"
    )
