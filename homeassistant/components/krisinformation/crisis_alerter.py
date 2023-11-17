"""Crisis Alerter from Krisinformation."""
import json
from typing import Any

import requests

API_BASE_URL = "https://api.krisinformation.se/v3/"


class Error(Exception):
    """Base class for exceptions in this module."""


class CrisisAlerter:
    """Crisis Alerter from Krisinformation."""

    def __init__(self, county: str | None = None, language: str = "sv") -> None:
        """Initialize the sensor."""
        self.language = language
        self.county = county

    def news(
        self,
        counties: str | None = None,
        all_counties: bool = False,
        days: int | None = None,
        number_of_news_articles: int | None = None,
        use_centralized_no_of_articles: bool = False,
        include_test: bool = False,
    ) -> list:
        """Fetch news from Krisinformation."""
        return self.request_builder(
            "news",
            language=self.language,
            counties=counties,
            allCounties=all_counties,
            days=days,
            numberOfNewsArticles=number_of_news_articles,
            useCentralizedNoOfArticles=use_centralized_no_of_articles,
            includeTest=include_test,
        )

    def vmas(
        self,
        counties: str | None = None,
        all_counties: bool = False,
        is_test: bool = False,
    ) -> list:
        """Fetch VMA from Krisinformation."""
        if is_test:
            # Return a test example of a VMA
            return self.request_builder("testvmas")
        return self.request_builder(
            "vmas",
            language=self.language,
            counties=counties,
            allCounties=all_counties,
        )

    def notifications(
        self,
        include_draft_notifications: bool = False,
        include_test_notifications: bool = False,
    ) -> list:
        """Retrieve editorial notifications (push notifications in the app) from Krisinformation."""
        return self.request_builder(
            "notifications",
            includeDraftNotifications=include_draft_notifications,
            includeTestNotifications=include_test_notifications,
        )

    def right_nows(self, counties: str | None = None) -> list:
        """Retrieve 'Current News' blocks from crisis information."""
        return self.request_builder(
            "rightnows",
            language=self.language,
            counties=counties,
        )

    def custom_feeds(self, feeds: str | None = None, days: int = 7) -> list:
        """Retrieve custom feeds from Krisinformation, SMHI (1) and Travikverket (2)."""
        return self.request_builder(
            "customfeeds",
            feeds=feeds,
            days=days,
        )

    def features(self, counties: str | None = None) -> list:
        """Retrieve 'Prepare yourself'-pages from Krisinformation."""
        return self.request_builder(
            "features",
            language=self.language,
            counties=counties,
        )

    def top_stories(
        self, counties: str | None = None, all_counties: bool | None = None
    ) -> list:
        """Retrieve 'Top Stories' from Krisinformation."""
        return self.request_builder(
            "topstories",
            language=self.language,
            counties=counties,
            allCounties=all_counties,
        )

    def request_builder(self, service, **parameters) -> Any:
        """Request builder."""
        urlformat = "{baseurl}/{service}?{parameters}&format=json"
        url = urlformat.format(
            baseurl=API_BASE_URL,
            service=service,
            parameters="&".join(
                [f"{key}={value}" for key, value in parameters.items()]
            ),
        )
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return json.loads(res.content.decode("UTF-8"))
        raise Error("Error: " + str(res.status_code) + str(res.content))
