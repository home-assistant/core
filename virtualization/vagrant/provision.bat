@echo off
call:main %*
goto:eof

:usage
echo.############################################################
echo.
echo.Use `./provision.bat` to interact with HASS. E.g:
echo.
echo.- setup the environment: `./provision.bat start`
echo.- restart HASS process: `./provision.bat restart`
echo.- run test suit: `./provision.bat tests`
echo.- destroy the host and start anew: `./provision.bat recreate`
echo.
echo.Official documentation at https://home-assistant.io/docs/installation/vagrant/
echo.
echo.############################################################'
goto:eof

:main
if "%*"=="setup" (
    if exist setup_done del setup_done
    vagrant up --provision
    copy /y nul setup_done
) else (
if "%*"=="tests" (
    copy /y nul run_tests
    vagrant provision
) else (
if "%*"=="restart" (
    copy /y nul restart
    vagrant provision
) else (
if "%*"=="start" (
    vagrant up --provision
) else (
if "%*"=="stop" (
    vagrant halt
) else (
if "%*"=="destroy" (
    vagrant destroy -f
) else (
if "%*"=="recreate" (
    if exist setup_done del setup_done
    if exist restart del restart
    vagrant destroy -f
    vagrant up --provision
) else (
    call:usage
)))))))
