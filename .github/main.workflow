workflow "Python 3.7 - tox" {
  on = "push"
  resolves = ["Python 3.7 - tests"]
}

action "Python 3.7 - tests" {
  uses = "home-assistant/actions/py37-tox@master"
  args = "-e py37"
}

workflow "Python 3.6 - tox" {
  on = "push"
  resolves = ["Python 3.6 - tests"]
}

action "Python 3.6 - tests" {
  uses = "home-assistant/actions/py36-tox@master"
  args = "-e py36"
}

workflow "Python 3.5 - tox" {
  on = "push"
  resolves = ["Python 3.5 - tests", "Python 3.5 - lint", "Python 3.5 - pylint", "Python 3.5 - typing", "Python 3.5 - cov"]
}

action "Python 3.5 - tests" {
  uses = "home-assistant/actions/py35-tox@master"
  args = "-e py35"
}

action "Python 3.5 - lint" {
  uses = "home-assistant/actions/py35-tox@master"
  args = "-e lint"
}

action "Python 3.5 - pylint" {
  uses = "home-assistant/actions/py35-tox@master"
  args = "-e pylint"
}

action "Python 3.5 - typing" {
  uses = "home-assistant/actions/py35-tox@master"
  args = "-e typing"
}

action "Python 3.5 - cov" {
  uses = "home-assistant/actions/py35-tox@master"
  args = "-e cov"
}
