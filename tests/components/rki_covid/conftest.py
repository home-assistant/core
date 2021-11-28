"""global fixtures for tests."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_parser():
    """Create a mock parser instance."""
    with patch(
        "rki_covid_parser.districts",
        return_values=[Mock()],
    ) as mock_parser:
        yield mock_parser
