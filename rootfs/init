#!/bin/execlineb -S0

##
## load default PATH (the same that Docker includes if not provided) if it doesn't exist,
## then go ahead with stage1.
## this was motivated due to this issue:
## - https://github.com/just-containers/s6-overlay/issues/108
##

/bin/importas -D /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PATH PATH
export PATH ${PATH}

##
## Skip further init if the user has a given CMD.
## This is to prevent Home Assistant from starting twice if the user
## decided to override/start via the CMD.
##

ifelse { s6-test $# -ne 0 }
{
  $@
}
/etc/s6/init/init-stage1 $@