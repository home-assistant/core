"""Tests for the azure_data_explorer integration."""

# fixtures for both init and config flow tests
from dataclasses import dataclass


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    entity_id: str
    expect_called: bool
