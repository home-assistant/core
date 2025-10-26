# Sony Projector test guidelines

- Prefer `MockConfigEntry` from `tests.common` to construct entries for this integration.
- Patch or stub out `ProjectorClient` interactions with `AsyncMock` objects; never import or rely on the real `pysdcp` library in tests.
- Use the shared `conftest.py` stub for `pysdcp` so tests never import the real dependency or duplicate stubbing logic.
- When asserting repairs issues, inspect the awaited call arguments (for example, `mock_issue.await_args`) instead of relying on private attributes.
- Annotate Home Assistant fixtures (for example, `hass: HomeAssistant`, `caplog: pytest.LogCaptureFixture`) so `pylint`'s custom plugins accept the tests without extra disables.
- Include a brief module-level docstring summarizing each test module's focus to keep pylint and future contributors aligned on the coverage intent.
- Import mocking utilities like `AsyncMock`, `MagicMock`, `patch`, and `call` from `unittest.mock` to keep linting happy and avoid mixing helper sources.
