import httpx
import urllib.parse
import json

class CanvasAPI:
    """A wrapper for the Canvas API."""

    def __init__(self, host: str, access_token: str) -> None:
        """Initialize the wrapper with the host and access token."""
        self.host = host
        self.access_token = access_token

    async def async_make_get_request(
        self, endpoint: str, parameters: dict = {}
    ) -> dict:
        """Make a request to a specified endpoint of the Canvas API."""

        headers = {"Authorization": "Bearer " + self.access_token}
        parameters_string = urllib.parse.urlencode(parameters)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.host + endpoint + "?" + parameters_string, headers=headers
            )

        return response

    async def async_test_authentication(self) -> bool:
        """Test authentication by making a dummy request to the Canvas API."""
        response = await self.async_make_get_request("/courses")

        return response.status_code == 200

    async def async_get_courses(self) -> list:
        """Retrieve a list of courses from the Instructure API."""
        response = await self.async_make_get_request("/courses", {"per_page": "50"})
        courses = json.loads(response.content.decode('utf-8'))
        return courses

    async def async_get_assignments(self, course_id) -> list:
        """Retrieve a list of assignments from the Canvas API."""
        response = await self.async_make_get_request(f"/courses/{course_id}/assignments", {"per_page": "50"})
        assignments = json.loads(response.content.decode('utf-8'))
        return assignments

    async def async_get_announcements(self) -> list:
        """Retrieve a list of announcements from the Canvas API.

        TODO - implement this function"""
        pass

    async def async_get_conversations(self, course_id) -> list:
        """Retrieve a list of conversations from the Instructure API."""
        response = await self.async_make_get_request(f"/conversations", {"per_page": "50"})
        assignments = json.loads(response.content.decode('utf-8'))
        return assignments