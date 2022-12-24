"""Constants for the Mastodon integration."""

import logging
from typing import Final

LOGGER = logging.getLogger(__name__)

CONF_BASE_URL: Final = "base_url"
DEFAULT_URL: Final = "https://mastodon.social"

# additional parameters that can be added to a send message call
# for details, see https://mastodonpy.readthedocs.io/en/1.8.0/05_statuses.html#mastodon.Mastodon.status_post
ACCEPTABLE_ADDITIONAL_PARAMS = [
    "visibility",
    "spoiler_text",
    "language",
]
