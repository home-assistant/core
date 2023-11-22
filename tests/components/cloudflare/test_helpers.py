"""Test Cloudflare integration helpers."""
from homeassistant.components.cloudflare.helpers import get_zone_id


def test_get_zone_id():
    """Test get_zone_id."""
    zones = [
        {"id": "1", "name": "example.com"},
        {"id": "2", "name": "example.org"},
    ]
    assert get_zone_id("example.com", zones) == "1"
    assert get_zone_id("example.org", zones) == "2"
    assert get_zone_id("example.net", zones) is None
