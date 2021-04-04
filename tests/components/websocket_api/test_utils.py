"""Test websocket_api helpers."""
from datetime import timedelta

from homeassistant.components.websocket_api.utils import SubscribeTriggerJSONEncoder


def test_json_encoder(hass):
    """Test the SubscribeTriggerJSONEncoder."""
    ha_json_enc = SubscribeTriggerJSONEncoder()

    # Test serializing a timedelta
    data = timedelta(
        days=1,
        hours=2,
        minutes=3,
    )
    assert ha_json_enc.default(data) == data.total_seconds()
