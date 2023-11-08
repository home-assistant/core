"""Crisis Alerter from Krisinformation"""
import requests
import json

API_BASE_URL = "https://api.krisinformation.se/v3/"


class Error(Exception):
    pass


class CrisisAlerter:
    """Crisis Alerter from Krisinformation"""

    def __init__(self, language: str = "sv", location: str | None = None):
        self.language = language
        self.location = location

    def get_news(
        self,
        counties: str | None = None,
        all_counties: bool | None = None,
        days: int | None = None,
        number_of_news_articles: int | None = None,
        use_centralized_no_of_articles: bool = False,
        include_test: bool = False,
    ):
        """Get news"""
        return self.request_builder(
            "news",
            language=self.language,
            counties=counties,
            allCounites=all_counties,
            days=days,
            numberOfNewsArticles=number_of_news_articles,
            useCentralizedNoOfArticles=use_centralized_no_of_articles,
            includeTest=include_test,
        )

    def request_builder(self, service, **parameters):
        """request builder"""
        urlformat = "{baseurl}/{service}?{parameters}&format=json"
        url = urlformat.format(
            baseurl=API_BASE_URL,
            service=service,
            parameters="&".join(
                ["{}={}".format(key, value) for key, value in parameters.items()]
            ),
        )
        res = requests.get(url)
        if res.status_code == 200:
            return json.loads(res.content.decode("UTF-8"))
        else:
            raise Error("Error: " + str(res.status_code) + str(res.content))
