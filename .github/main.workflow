workflow "Tox" {
  on = "push"
  resolves = ["Python 3.7", "Python 3.6", "Python 3.5"]
}

action "Python 3.7" {
  uses = "home-assistant/actions/py37-tox@master"
  args = "-e lint,pylint,typing,cov"
}

action "Python 3.6" {
  uses = "home-assistant/actions/py36-tox@master"
  args = "-e lint,pylint,typing"
}

action "Python 3.5" {
  uses = "home-assistant/actions/py35-tox@master"
  args = "-e lint,pylint,typing"
}
