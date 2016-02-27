**Description:**


**Related issue (if applicable):** #
**Example entry for `configuration.yaml` (if applicable):**
```yaml

```

**Checklist:**

- [ ] Local tests with `tox` ran successfully.
- [ ] No CI failures. **Your PR cannot be merged unless CI is green!**
- [ ] [Fork is up to date][fork] and was rebased on the `dev` branch before creating the PR.
- If code communicates with devices:
  - [ ] 3rd party library/libraries for communication is/are added as dependencies via the `REQUIREMENTS` variable ([example][ex-requir]).
  - [ ] 3rd party dependencies are imported inside functions that use them ([example][ex-import]).
  - [ ] `requirements_all.txt` is up-to-date, `script/gen_requirements_all.py` ran and the updated file is included in the PR.
  - [ ] New files were added to `.coveragerc`.
- If the code does not depend on external Python module:
  - [ ] Tests to verify that the code works are included.
- [ ] [Commits will be squashed][squash] when the PR is ready to be merged.

[fork]: http://stackoverflow.com/a/7244456
[squash]: https://github.com/ginatrapani/todo.txt-android/wiki/Squash-All-Commits-Related-to-a-Single-Issue-into-a-Single-Commit
[ex-requir]: https://github.com/balloob/home-assistant/blob/dev/homeassistant/components/keyboard.py#L16
[ex-import]: https://github.com/balloob/home-assistant/blob/dev/homeassistant/components/keyboard.py#L51

