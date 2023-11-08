import httpx


class ApiWrapper:
    def __init__(self, host: str, access_token: str) -> None:
        self.host = host
        self.access_token = access_token

    async def test_auth(self) -> bool:
        """Test authentication by making a dummy request to the Canvas API."""

        headers = {"Authorization": "Bearer " + self.access_token}

        async with httpx.AsyncClient() as client:
            response = await client.get(self.host + "/courses", headers=headers)

        return response.status_code == 200
