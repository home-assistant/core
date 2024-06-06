"""API client for Leslie's Pool Water Tests."""

from bs4 import BeautifulSoup, Tag
import requests


class LesliesPoolApi:
    """API class to interact with Leslie's Pool service."""

    LOGIN_PAGE_URL = "https://lesliespool.com/on/demandware.store/Sites-lpm_site-Site/en_US/Account-Show"
    LOGIN_URL = "https://lesliespool.com/on/demandware.store/Sites-lpm_site-Site/en_US/Account-Login"
    WATER_TEST_URL = "https://lesliespool.com/on/demandware.store/Sites-lpm_site-Site/en_US/WaterTest-GetWaterTest"

    def __init__(
        self, username: str, password: str, pool_profile_id: str, pool_name: str
    ) -> None:
        """Initialize the API with user credentials and pool details."""
        self.username = username
        self.password = password
        self.pool_profile_id = pool_profile_id
        self.pool_name = pool_name
        self.session = requests.Session()

    def authenticate(self) -> bool:
        """Authenticate the user and start a session."""
        response = self.session.get(self.LOGIN_PAGE_URL)
        soup = BeautifulSoup(response.text, "html.parser")
        csrf_token_tag = soup.find("input", {"name": "csrf_token"})

        csrf_token = None
        if isinstance(csrf_token_tag, Tag) and csrf_token_tag.has_attr("value"):
            csrf_token = csrf_token_tag["value"]

        if not csrf_token:
            return False

        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "user-agent": "Mozilla/5.0",
        }

        payload = {
            "loginEmail": self.username,
            "loginPassword": self.password,
            "csrf_token": csrf_token,
        }

        login_response = self.session.post(
            self.LOGIN_URL, headers=headers, data=payload
        )
        return login_response.status_code == 200

    def fetch_water_test_data(self) -> dict:
        """Fetch water test data for the pool."""
        self.session.get(
            f"https://lesliespool.com/on/demandware.store/Sites-lpm_site-Site/en_US/WaterTest-Landing?poolProfileId={self.pool_profile_id}&poolName={self.pool_name}"
        )
        cookies = self.session.cookies.get_dict()
        cookie_header = "; ".join([f"{key}={value}" for key, value in cookies.items()])

        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "cookie": cookie_header,
            "user-agent": "Mozilla/5.0",
        }

        payload = "poolProfileName=Pool&poolSanitizer=Salt+3000-4000"
        response = self.session.post(self.WATER_TEST_URL, headers=headers, data=payload)
        data = response.json()

        html_content = data["response"]
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find(
            "table", class_="table table-striped table-bordered table-hover table-sm"
        )

        values = {}
        if isinstance(table, Tag):
            first_row_tag = table.find("tbody")
            if isinstance(first_row_tag, Tag):
                first_row = first_row_tag.find("tr")
                if isinstance(first_row, Tag):
                    columns = first_row.find_all("td")
                    if len(columns) > 10:
                        values = {
                            "free_chlorine": columns[1].text.strip(),
                            "total_chlorine": columns[2].text.strip(),
                            "ph": columns[3].text.strip(),
                            "alkalinity": columns[4].text.strip(),
                            "calcium": columns[5].text.strip(),
                            "cyanuric_acid": columns[6].text.strip(),
                            "iron": columns[7].text.strip(),
                            "copper": columns[8].text.strip(),
                            "phosphates": columns[9].text.strip(),
                            "salt": columns[10].text.strip(),
                        }

        return values
