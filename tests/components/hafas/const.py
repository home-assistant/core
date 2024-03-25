"""Constants for the HaFAS integration tests."""

from datetime import datetime

from homeassistant.components.hafas.config_flow import Profile
from homeassistant.util.dt import UTC

TEST_STATION1 = "Berlin Hbf"
TEST_STATION2 = "Leipzig Hbf"
TEST_PROFILE = Profile.DB
TEST_OFFSET = {"seconds": 0}
TEST_ONLY_DIRECT = False
TEST_TIME = datetime(2022, 10, 1, 12, 0, 0, tzinfo=UTC)
