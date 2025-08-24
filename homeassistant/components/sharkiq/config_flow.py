import urllib.parse

async def do_auth0_login(session, username, password):
    AUTH_DOMAIN = "https://login.sharkninja.com"
    CLIENT_ID = "wsguxrqm77mq4LtrTrwg8ZJUxmSrexGi"
    REDIRECT_URI = "com.sharkninja.shark://login.sharkninja.com/ios/com.sharkninja.shark/callback"
    SCOPE = "openid profile email offline_access"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": AUTH_DOMAIN,
        "Referer": AUTH_DOMAIN + "/",
    }

    # 1. GET /authorize
    authorize_url = (
        f"{AUTH_DOMAIN}/authorize?"
        + urllib.parse.urlencode(
            {
                "os": "android",
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
            }
        )
    )
    async with session.get(authorize_url, headers=HEADERS, allow_redirects=True) as resp:
        parsed = urllib.parse.urlparse(str(resp.url))
        state = urllib.parse.parse_qs(parsed.query).get("state", [None])[0]
    if not state:
        raise CannotConnect("No state returned from authorize")

    # 2. POST /u/login
    login_url = f"{AUTH_DOMAIN}/u/login?state={state}"
    form_data = {"state": state, "username": username, "password": password, "action": "default"}
    async with session.post(login_url, headers=HEADERS, data=form_data, allow_redirects=False) as resp:
        redirect_url = resp.headers.get("Location")

    code = None
    if redirect_url and redirect_url.startswith("/authorize/resume"):
        resume_url = AUTH_DOMAIN + redirect_url
        async with session.get(resume_url, headers=HEADERS, allow_redirects=False) as resp:
            final_url = resp.headers.get("Location")
            if final_url:
                parsed = urllib.parse.urlparse(final_url)
                code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
    else:
        parsed = urllib.parse.urlparse(redirect_url or "")
        code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]

    if not code:
        raise CannotConnect("No authorization code received")

    # 3. Exchange code for tokens
    token_url = f"{AUTH_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    async with session.post(token_url, headers={"Content-Type": "application/json"}, json=payload) as resp:
        token_data = await resp.json()
    if "access_token" not in token_data:
        raise InvalidAuth("Auth0 did not return an access token")

    return token_data
