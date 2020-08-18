"""Test attributes common to all entity types."""
import hdate

from homeassistant.components import jewish_calendar


def test_prefix():
    """Test sensor prefix."""
    location = hdate.Location(
        name="Jerusalem",
        latitude=31.778,
        longitude=35.235,
        timezone="Asia/Jerusalem",
        altitude=754,
        diaspora=False,
    )
    language = "English"
    candle_lighting_offset = 18
    havdalah_offset = 50

    prefix = jewish_calendar.get_unique_prefix(
        location, language, candle_lighting_offset, havdalah_offset
    )
    assert prefix == "jcal_36dee62e059a0ad88a91af0824025175"
