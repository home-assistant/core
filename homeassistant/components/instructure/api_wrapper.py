import httpx
import urllib.parse
import json

class ApiWrapper:
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

    async def async_get_assignments(self, course_id: int) -> list:
        """Retrieve a list of assignments from the Canvas API."""

        return [
            {
            "id": 76160,
            "due_at": "2023-08-30T21:59:59Z",
            "course_id": 25271,
            "name": "First Assignment",
            "html_url": "https://chalmers.instructure.com/courses/25271/assignments/76160"
            },
            {
            "id": 76161,
            "due_at": "2023-09-30T21:59:59Z",
            "course_id": 25271,
            "name": "Second Assignment",
            "html_url": "https://chalmers.instructure.com/courses/25271/assignments/76160"
            },

            {
            "id": 76162,
            "due_at": "2023-10-30T21:59:59Z",
            "course_id": 25271,
            "name": "Third Assignment",
            "html_url": "https://chalmers.instructure.com/courses/25271/assignments/76160"
            }
        ]

    async def async_get_announcements(self) -> list:
        """Retrieve a list of announcements from the Canvas API.

        TODO - implement this function"""
        pass

    async def async_get_conversations(self) -> list:
        """Retrieve a list of conversations from the Instructure API."""
        response = await self.async_make_get_request("/conversations", {"per_page": "50"})
        conversations = json.loads(response.content.decode('utf-8'))
        return conversations