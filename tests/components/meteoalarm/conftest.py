"""Fixtures for the MeteoAlarm integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

ALERT = {
    "language": "en-GB",
    "category": "Met",
    "event": "Moderate wind warning",
    "responseType": "Monitor",
    "urgency": "Future",
    "severity": "Moderate",
    "certainty": "Likely",
    "effective": "2026-01-01T08:00:00+00:00",
    "onset": "2026-01-01T10:00:00+00:00",
    "expires": "2026-01-01T18:00:00+00:00",
    "senderName": "Test weather service",
    "headline": "Moderate wind warning. Test province",
    "description": "Maximum gusts of 70 km/h.",
    "instruction": "Be prepared.",
    "awareness_level": "2; yellow; Moderate",
    "awareness_type": "1; Wind",
    "identifier": "2.49.0.0.528.0.TEST.20260101080000.1",
    "message_type": "Alert",
    "references": None,
    "sent": "2026-01-01T08:00:00+00:00",
}


@pytest.fixture
def mock_meteoalert() -> Generator[MagicMock]:
    """Mock the Meteoalert client with an alert that is still valid."""
    with patch(
        "homeassistant.components.meteoalarm.binary_sensor.Meteoalert",
        autospec=True,
    ) as mock_class:
        mock_class.return_value.get_alert.return_value = dict(ALERT)
        yield mock_class
