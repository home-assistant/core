"""Constants for krisinformation tests."""
from homeassistant.components.krisinformation.const import CONF_COUNTY, COUNTY_CODES
from homeassistant.const import CONF_NAME

MOCK_CONFIG = {
    CONF_NAME: "Krisinformation test",
    CONF_COUNTY: COUNTY_CODES["17"],
}
