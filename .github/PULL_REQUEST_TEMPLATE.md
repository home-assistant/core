**Description:**


**Related issue (if applicable):** #

**Example entry for `configuration.yaml` (if applicable):**
```yaml

```

**Checklist:**

- [ ] Local tests with `tox` run successfully.
- [ ] TravisCI does not fail. **Your PR cannot be merged unless CI is green!**
- [ ] [Fork is up to date][fork] and was rebased on the `dev` branch before creating the PR.
- [ ] Commits have been [squashed][squash].
- If code communicates with devices:
  - [ ] New dependencies have been added to the `REQUIREMENTS` variable ([example][ex-requir]).
  - [ ] New dependencies are only imported inside functions that use them ([example][ex-import]).
  - [ ] New dependencies have been added to `requirements_all.txt` by running `script/gen_requirements_all.py`.
  - [ ] New files were added to `.coveragerc`.
- If the code does not interact with devices:
  - [ ] Tests have been added to verify that the new code works.

[fork]: http://stackoverflow.com/a/7244456
[squash]: https://github.com/ginatrapani/todo.txt-android/wiki/Squash-All-Commits-Related-to-a-Single-Issue-into-a-Single-Commit
[ex-requir]: https://github.com/balloob/home-assistant/blob/dev/homeassistant/components/keyboard.py#L16
[ex-import]: https://github.com/balloob/home-assistant/blob/dev/homeassistant/components/keyboard.py#L51

