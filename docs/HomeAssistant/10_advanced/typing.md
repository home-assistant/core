---
title: "Adding type hints to your code"
---

Type hints in Python are static annotations of variables and functions, to let humans more easily understand the code. See the standard library [docs](https://docs.python.org/3/library/typing.html) and this PyCascades 2018 [talk](https://youtu.be/zKre4DKAB30).

Type hints are not required for all modules at the moment in Home Assistant, but we aim to have a complete as possible coverage.
To improve and encourage this, all code is type checked in our continuous integration process and assumes everything is type checked, unless explicitly excluded from type checking.

Adding type hints to an existing codebase can be a daunting task. To speed this up and help developers doing this, Instagram made the [`monkeytype`](https://pypi.org/project/MonkeyType/) program. It will analyze calls during runtime and try to assign the correct type hints to the code.

See [this instagram blog post](https://instagram-engineering.com/let-your-code-type-hint-itself-introducing-open-source-monkeytype-a855c7284881) for a description of the workflow involved to use the monkeytype program.

We've added a script to start a run of our test suite or a test module and tell the `monkeytype` program to analyze the run.

### Basic workflow

1. Run `script/monkeytype tests/path/to/your_test_module.py`.
2. Run `monkeytype stub homeassistant.your_actual_module`.
3. Look at output from the monkeytyped typing stub. If not totally bad, apply the stub to your module. You most likely will need to manually edit the typing in the last step.
4. Run `monkeytype apply homeassistant.your_actual_module`.
5. Check the diff and manually correct the typing if needed. Commit, push the branch and make a PR.

**Note:**
Applying a monkeytyped stub to a module that has existing typing annotations might error and not work. This tool is most useful for totally untyped modules.

### Including modules for strict type checking

While we encourage the use of type hints, we currently do not require them for our integrations.
By default, our CI checks statically for type hints. In case a module has been fully typed, it can be
marked for enabling strict checks, by adding the module to the `.strict-typing` file
that is located at the root of the Home Assistant Core project.
