"""Constants for Reddit platform."""

from __future__ import annotations

from typing import Final

CONF_SORT_BY: Final = "sort_by"
CONF_SUBREDDITS: Final = "subreddits"

ATTR_BODY: Final = "body"
ATTR_COMMENTS_NUMBER: Final = "comms_num"
ATTR_CREATED: Final = "created"
ATTR_POSTS: Final = "posts"
ATTR_SUBREDDIT: Final = "subreddit"
ATTR_SCORE: Final = "score"
ATTR_TITLE: Final = "title"
ATTR_URL: Final = "url"

DEFAULT_NAME: Final = "Reddit"

LIST_TYPES: Final[list[str]] = ["top", "controversial", "hot", "new"]
