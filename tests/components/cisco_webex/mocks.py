"""Mocks used for testing cisco_webex integration."""
import webexteamssdk
from webexteamssdk import WebexTeamsAPI


class MockWebexTeamsAPI(WebexTeamsAPI):
    """Mocked WebexTeamsAPI that doesn't do anything."""

    def __init__(self, access_token):
        """Blank init."""
        self.people = MockPeopleAPI()


class MockPeopleAPI:
    """Mock PeopleAPI."""

    def me(self):
        """Mock me."""
        return MockPerson()

    def list(self, email):
        """Mock list."""
        return [MockPerson()]

    def get(self, user_id):
        """Mock get."""
        return MockPerson()


class MockPerson:
    """Mock Person object."""

    @property
    def id(self):
        """Mock id."""
        return "77777"

    def to_dict(self):
        """Mock to_dict."""
        return {}

    @property
    def type(self):
        """Mock type."""
        return "bot"

    @property
    def displayName(self):
        """Mock displayName."""
        return "Test user"

    @property
    def status(self):
        """Mock status."""
        return "active"

    @property
    def avatar(self):
        """Mock avatar."""
        return "http://www.com/pic.png"


class MockApiError(webexteamssdk.ApiError):
    """Mock for empty api error."""

    def __init__(self):
        """Mock init."""
        pass
