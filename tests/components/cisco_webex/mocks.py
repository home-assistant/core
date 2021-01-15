import webexteamssdk
from webexteamssdk import WebexTeamsAPI


class MockWebexTeamsAPI(WebexTeamsAPI):
    """Mocked WebexTeamsAPI that doesn't do anything."""

    def __init__(self, access_token):
        self.people = MockPeopleAPI()


class MockPeopleAPI:
    def me(self):
        return MockPerson()

    def list(self, email):
        return [MockPerson()]


class MockPerson:
    @property
    def type(self):
        return "bot"

    @property
    def displayName(self):
        return "Test user"


class MockApiError(webexteamssdk.ApiError):
    """Mock for empty api error"""

    def __init__(self):
        pass
