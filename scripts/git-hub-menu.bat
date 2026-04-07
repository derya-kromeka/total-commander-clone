@echo off
setlocal EnableDelayedExpansion
REM Git / GitHub all-in-one menu (Windows).
REM Put this file in:  YOUR_PROJECT\scripts\git-hub-menu.bat
REM Project root: one folder above this script, OR GIT_MENU_PROJECT_ROOT, OR %%1
REM Run from any folder: full path to this .bat (no cd needed).

set "PROJECT_ROOT="
REM Resolve paths with FOR — not "cd" + %%CD%% inside (...) blocks, which breaks:
REM %%CD%% expands before "cd" runs, so PROJECT_ROOT could stay the launch folder (e.g. scripts\).
if defined GIT_MENU_PROJECT_ROOT (
  if exist "%GIT_MENU_PROJECT_ROOT%\" (
    for %%I in ("%GIT_MENU_PROJECT_ROOT%\.") do set "PROJECT_ROOT=%%~fI"
  )
)
if not defined PROJECT_ROOT (
  if not "%~1"=="" (
    if exist "%~f1\" (
      for %%I in ("%~f1\.") do set "PROJECT_ROOT=%%~fI"
    )
  )
)
if not defined PROJECT_ROOT (
  for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
)

:menu
cls
echo ==========================================
echo   Git / GitHub helper
echo ==========================================
echo   Project root: %PROJECT_ROOT%
echo   This script:  %~f0
echo ==========================================
echo.

call :print_menu_context
echo   1 - Check Git / install instructions
echo   2 - Init repository here ^(git init, branch main^)
echo   3 - Set or change remote origin ^(GitHub URL^)
echo   4 - Pull from GitHub ^(pull --rebase + status^)
echo   5 - Status ^(full^)
echo   6 - Save to GitHub ^(add all + commit + push^)
echo   7 - Set my name and email ^(git config --global^)
echo   8 - First-time wizard ^(init + remote + first push^)
echo   9 - How to clone on another PC
echo  10 - Force push ^(after history rewrite; --force-with-lease^)
echo  11 - GitHub HTTPS token - how-to + save ^(fixes 401^)
echo  12 - Diagnose push/auth/remote errors ^(401, repository not found^)
echo   0 - Exit
echo.
set /p CHOICE=Enter choice [0-12]: 

if "%CHOICE%"=="1" goto check_git
if "%CHOICE%"=="2" goto init_repo
if "%CHOICE%"=="3" goto set_remote
if "%CHOICE%"=="4" goto pull
if "%CHOICE%"=="5" goto status
if "%CHOICE%"=="6" goto commit_push
if "%CHOICE%"=="7" goto identity
if "%CHOICE%"=="8" goto first_time
if "%CHOICE%"=="9" goto clone_help
if "%CHOICE%"=="10" goto force_push
if "%CHOICE%"=="11" goto github_token
if "%CHOICE%"=="12" goto diagnose_push_auth
if "%CHOICE%"=="0" goto eof
echo Unknown option.
timeout /t 2 >nul
goto menu

:check_git
where git >nul 2>&1
if errorlevel 1 (
  echo.
  echo Git is not installed or not in PATH.
  echo.
  echo Install:
  echo   https://git-scm.com/download/win
  echo Or in PowerShell/cmd ^(may need admin^):
  echo   winget install --id Git.Git -e --source winget
  echo.
  echo After installing, CLOSE and reopen this window, then run this script again.
) else (
  git --version
)
pause
goto menu

:init_repo
where git >nul 2>&1
if errorlevel 1 goto need_git
if exist "%PROJECT_ROOT%\.git" (
  echo Already a Git repository ^(.git exists^).
  pause
  goto menu
)
cd /d "%PROJECT_ROOT%"
git init
git branch -M main
echo Done.
pause
goto menu

:set_remote
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo yet. Use option 2 first.
  pause
  goto menu
)
echo Paste GitHub repo URL ^(HTTPS or git@... SSH^). Empty = cancel.
set /p URL=origin URL: 
if "!URL!"=="" set "GIT_MENU_FROM_COMMIT=" & echo Cancelled. & pause & goto menu
cd /d "%PROJECT_ROOT%"
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin "!URL!"
) else (
  echo Remote origin exists. Updating URL.
  git remote set-url origin "!URL!"
)
git remote -v
if defined GIT_MENU_FROM_COMMIT (
  set "GIT_MENU_FROM_COMMIT="
  echo.
  echo Continuing option 6: add, commit, push...
  goto commit_push
)
pause
goto menu

:pull
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo.
  pause
  goto menu
)
cd /d "%PROJECT_ROOT%"
echo git pull --rebase
git pull --rebase
if errorlevel 1 (
  call :banner_fail
) else (
  call :banner_success
)
echo git status
git status -sb
pause
goto menu

:status
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo.
  pause
  goto menu
)
cd /d "%PROJECT_ROOT%"
git status
pause
goto menu

:commit_push
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo.
  pause
  goto menu
)
cd /d "%PROJECT_ROOT%"
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo.
  echo No "origin" remote is set yet. You need your GitHub repo URL ^(HTTPS or SSH^).
  echo On GitHub: open your repo - green "Code" button - copy the URL.
  echo Then use menu option 3, or set remote now below.
  echo.
  set /p CP_OR=Set remote now? [y/N]: 
  if /I "!CP_OR!"=="y" set "GIT_MENU_FROM_COMMIT=1" & goto set_remote
  if /I "!CP_OR!"=="yes" set "GIT_MENU_FROM_COMMIT=1" & goto set_remote
  echo Cancelled.
  pause
  goto menu
)
set "GIT_UN="
set "GIT_UE="
for /f "delims=" %%a in ('git config user.name 2^>nul') do set "GIT_UN=%%a"
for /f "delims=" %%a in ('git config user.email 2^>nul') do set "GIT_UE=%%a"
if "!GIT_UN!"=="" goto commit_push_warn_identity
if "!GIT_UE!"=="" goto commit_push_warn_identity
:commit_push_after_identity
call :get_changelog_ver
if defined CHG_VER (
  echo Suggested from CHANGELOG.md: !CHG_VER!
  set /p MSG=Commit message [!CHG_VER!] ^(Enter = use version^): 
  if "!MSG!"=="" set MSG=!CHG_VER!
) else (
  set /p MSG=Commit message: 
)
if "!MSG!"=="" echo Empty message. Cancelled. & pause & goto menu
set "CUR_BRANCH="
for /f "delims=" %%b in ('git branch --show-current 2^>nul') do set "CUR_BRANCH=%%b"
if "!CUR_BRANCH!"=="" set "CUR_BRANCH=^(unknown^)"
echo.
echo Will run: git add -A  -^>  commit  -^>  push to origin ^(current branch: !CUR_BRANCH!^)
set /p CP_GO=Proceed? [Y/n]: 
if /I "!CP_GO!"=="n" echo Cancelled. & pause & goto menu
if /I "!CP_GO!"=="no" echo Cancelled. & pause & goto menu
git ls-remote --heads origin >nul 2>"%TEMP%\tcc-git-ls-remote.err"
if errorlevel 1 (
  echo.
  echo Could not reach the remote ^(offline, firewall, DNS, or missing auth for ls-remote^).
  echo You can fix credentials with option 11 or diagnosis with option 12.
  set /p CP_TRY=Try push anyway? [Y/n]: 
  if /I "!CP_TRY!"=="n" del /f /q "%TEMP%\tcc-git-ls-remote.err" 2>nul & pause & goto menu
  if /I "!CP_TRY!"=="no" del /f /q "%TEMP%\tcc-git-ls-remote.err" 2>nul & pause & goto menu
)
del /f /q "%TEMP%\tcc-git-ls-remote.err" 2>nul
echo.
git add -A
git diff --cached --quiet
if errorlevel 1 (
  set "GIT_MENU_COMMIT_MSG=!MSG!"
  set "COMMIT_MSG_FILE=%TEMP%\git-menu-commit-msg.txt"
  powershell -NoProfile -Command "$p = Join-Path $env:TEMP 'git-menu-commit-msg.txt'; [System.IO.File]::WriteAllText($p, $env:GIT_MENU_COMMIT_MSG, [System.Text.UTF8Encoding]::new($false))"
  git commit -F "!COMMIT_MSG_FILE!"
  if errorlevel 1 (
    del /f /q "!COMMIT_MSG_FILE!" 2>nul
    echo.
    echo Commit failed. Set user.name and user.email with option 7, or fix pre-commit hooks.
    call :banner_fail
    pause
    goto menu
  )
  del /f /q "!COMMIT_MSG_FILE!" 2>nul
) else (
  echo No new changes to commit ^(nothing different from your last commit^).
  echo That usually means everything is already saved in Git, or files are outside this folder.
  git rev-parse HEAD >nul 2>&1
  if errorlevel 1 (
    echo.
    echo You have no commits yet. Git only tracks files inside this folder:
    echo   %PROJECT_ROOT%
    echo Add or save your project files here, then run option 6 again ^(or use option 8^).
    call :banner_fail
    pause
    goto menu
  )
)
echo.
echo git push
git push 2>"%TEMP%\tcc-git-push.err"
if errorlevel 1 (
  echo.
  echo Push did not succeed. Tips:
  echo   Try:  git push -u origin main
  echo   Remote has commits:  git pull --rebase origin main  then push again.
  echo   Unrelated histories:  git pull origin main --allow-unrelated-histories --no-edit
  echo   HTTPS: use a Personal Access Token ^(option 11^), not your GitHub password.
  echo   Diagnosis: option 12.
  echo.
  echo Last lines from Git:
  powershell -NoProfile -Command "$p = Join-Path $env:TEMP 'tcc-git-push.err'; if (Test-Path $p) { Get-Content $p -Tail 12 }"
  del /f /q "%TEMP%\tcc-git-push.err" 2>nul
  call :banner_fail
) else (
  del /f /q "%TEMP%\tcc-git-push.err" 2>nul
  call :banner_success
)
pause
goto menu

:commit_push_warn_identity
echo.
echo Git user.name or user.email is not set. Commits will fail until you set them.
echo Use menu option 7 ^(global name/email^).
set /p CP_ID=Configure identity now? [y/N]: 
if /I "!CP_ID!"=="y" goto identity
if /I "!CP_ID!"=="yes" goto identity
echo Continuing anyway ^(commit may fail^).
goto commit_push_after_identity

:diagnose_push_auth
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo. Use option 2 first.
  pause
  goto menu
)
cls
echo ========== Diagnose push / auth / remote ==========
echo.
cd /d "%PROJECT_ROOT%"
set "ORIGIN_URL="
for /f "delims=" %%u in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%u"
if "!ORIGIN_URL!"=="" (
  echo No origin remote is set.
  echo Fix: use option 3 to set your GitHub repo URL.
  set /p GO_REMOTE=Open option 3 now? [Y/n]: 
  if /I "!GO_REMOTE!"=="n" goto diagnose_done
  goto set_remote
)
echo origin URL:
echo   !ORIGIN_URL!
echo.
echo Testing remote access: git ls-remote --heads origin
set "TMP_ERR=%TEMP%\git-menu-ls-remote.err"
if exist "!TMP_ERR!" del /f /q "!TMP_ERR!" >nul 2>&1
git ls-remote --heads origin >nul 2>"!TMP_ERR!"
if errorlevel 1 (
  echo Access test failed.
  echo Error output:
  if exist "!TMP_ERR!" (
    for /f "usebackq delims=" %%l in ("!TMP_ERR!") do echo   %%l
  )
  echo.
  findstr /I /C:"Repository not found" "!TMP_ERR!" >nul
  if not errorlevel 1 (
    echo Interpretation:
    echo   - Wrong remote URL, OR
    echo   - Repository is private and credentials are missing/invalid, OR
    echo   - Your account has no access to this repository.
    goto diagnose_helper
  )
  findstr /I /C:"Authentication failed" /C:"401" /C:"403" /C:"Invalid username or password" /C:"Missing or invalid credentials" /C:"could not read Username" "!TMP_ERR!" >nul
  if not errorlevel 1 (
    echo Interpretation:
    echo   - Credentials/token are missing, expired, or wrong for this repo.
    goto diagnose_helper
  )
  echo Interpretation:
  echo   - Network, auth, or URL issue. See error above.
) else (
  echo Remote access OK.
)

:diagnose_helper
echo.
echo Credential helper ^(repo-local^):
git config --local --get credential.helper
if errorlevel 1 echo   ^(not set^)
echo Credential helper ^(global^):
git config --global --get credential.helper
if errorlevel 1 echo   ^(not set^)
echo.
echo Quick fixes:
echo   1 - Set/change origin URL now
echo   2 - Save GitHub HTTPS token now
echo   Enter - Back
set /p FIX=Choice: 
if "!FIX!"=="1" goto set_remote
if "!FIX!"=="2" goto github_token

:diagnose_done
if exist "%TEMP%\git-menu-ls-remote.err" del /f /q "%TEMP%\git-menu-ls-remote.err" >nul 2>&1
pause
goto menu

:force_push
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo.
  pause
  goto menu
)
echo Force push overwrites the remote branch with your local history.
echo Use ONLY after a history rewrite or if you know why.
set /p CONF=Type YES to run git push --force-with-lease origin main: 
if not "!CONF!"=="YES" echo Cancelled. & pause & goto menu
cd /d "%PROJECT_ROOT%"
echo git push --force-with-lease origin main
git push --force-with-lease origin main
if errorlevel 1 (
  echo Fix errors above ^(auth, branch name^).
  call :banner_fail
) else (
  call :banner_success
)
pause
goto menu

:github_token
where git >nul 2>&1
if errorlevel 1 goto need_git
if not exist "%PROJECT_ROOT%\.git" (
  echo Not a Git repo. Use option 2 first.
  pause
  goto menu
)
cd /d "%PROJECT_ROOT%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\save-github-token.ps1"
pause
goto menu

:identity
where git >nul 2>&1
if errorlevel 1 goto need_git
echo Current global user.name:
git config --global user.name
echo Current global user.email:
git config --global user.email
echo.
set /p GNAME=Set user.name ^(empty = skip^): 
if not "!GNAME!"=="" git config --global user.name "!GNAME!"
set /p GEMAIL=Set user.email ^(empty = skip^): 
if not "!GEMAIL!"=="" git config --global user.email "!GEMAIL!"
echo.
git config --global --get user.name
git config --global --get user.email
pause
goto menu

:first_time
where git >nul 2>&1
if errorlevel 1 goto need_git
cd /d "%PROJECT_ROOT%"
if not exist ".git" (
  git init
  git branch -M main
)
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo Paste your GitHub repo URL ^(HTTPS or SSH^).
  echo Empty repo OR repo with README both work — if push fails, pull first: git pull --rebase origin main
  set /p URL=origin URL: 
  if not "!URL!"=="" git remote add origin "!URL!"
) else (
  echo Remote origin already set:
  git remote -v
)
call :get_changelog_ver
if defined CHG_VER (
  set /p MSG=First commit message [!CHG_VER!] ^(Enter = use version^): 
  if "!MSG!"=="" set MSG=!CHG_VER!
) else (
  set /p MSG=First commit message [Initial commit]: 
  if "!MSG!"=="" set MSG=Initial commit
)
git add -A
git diff --cached --quiet
if errorlevel 1 goto first_commit_done
echo No new changes to stage ^(nothing different from what Git already has^).
echo If this is your first commit and the folder looks empty to Git, we add a tiny .gitkeep file.
if not exist "%PROJECT_ROOT%\.gitkeep" (
  powershell -NoProfile -Command "Set-Content -LiteralPath (Join-Path '%PROJECT_ROOT%' '.gitkeep') -Encoding utf8 -Value '# Placeholder so the first commit has a file. You can delete this after real files are tracked.'"
)
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "!MSG!"
  goto first_push
)
git rev-parse HEAD >nul 2>&1
if not errorlevel 1 (
  echo.
  echo Your repo already has commits ^(everything may already be saved^).
  echo Use option 6 when you change files, or option 4 to pull from GitHub.
  call :banner_success
  pause
  goto menu
)
echo Creating an empty first commit ^(allowed by Git^) so you can push to GitHub...
git commit --allow-empty -m "!MSG!"
if errorlevel 1 (
  call :banner_fail
  pause
  goto menu
)
goto first_push
:first_commit_done
git commit -m "!MSG!"
:first_push
git remote get-url origin >nul 2>&1
if errorlevel 1 (
  echo No origin remote. Use option 3, then option 6.
  pause
  goto menu
)
echo Fetching origin...
git fetch origin 2>nul
git rev-parse origin/main >nul 2>&1
if not errorlevel 1 (
  echo If GitHub already has commits ^(README^), pull before push:
  echo   git pull --rebase origin main
  echo If you see unrelated histories:
  echo   git pull origin main --allow-unrelated-histories --no-edit
  echo.
)
echo git push -u origin main
git push -u origin main
if errorlevel 1 (
  echo.
  echo Push failed. Try: git pull --rebase origin main
  echo Then push again. HTTPS needs a token ^(option 11 on this menu^).
  echo Unrelated histories: git pull origin main --allow-unrelated-histories --no-edit
  call :banner_fail
) else (
  call :banner_success
)
pause
goto menu

:clone_help
echo.
echo ----- Clone this repo on ANOTHER computer -----
echo 1. Install Git for Windows.
echo 2. On GitHub: green Code button - copy HTTPS or SSH URL.
echo 3. Run:  git clone ^<URL^> ^<folder-name^>
echo 4. Open folder in Cursor. Each session: Pull ^(option 4^).
echo 5. When done: Save to GitHub ^(option 6^).
echo.
pause
goto menu

:need_git
echo Git not found. Use option 1 for install links.
pause
goto menu

:banner_success
echo.
echo **********************************************************************
echo *  SUCCESS                                                           *
echo **********************************************************************
echo.
exit /b 0

:banner_fail
echo.
echo **********************************************************************
echo *  FAILED                                                            *
echo **********************************************************************
echo.
exit /b 0

REM Summary under the menu: origin, identity, HTTPS token file ^(no network test^).
:print_menu_context
set "CTX_ORIG="
set "CTX_UN="
set "CTX_UE="
where git >nul 2>&1
if errorlevel 1 (
  echo   Git: NOT FOUND - use option 1
  exit /b 0
)
for /f "delims=" %%v in ('git --version') do echo   %%v
if not exist "%PROJECT_ROOT%\.git" (
  echo   ^(This folder is not a Git repo yet — use option 2^)
  exit /b 0
)
echo   --- This repo ^(quick summary^) ---
for /f "delims=" %%u in ('git -C "%PROJECT_ROOT%" remote get-url origin 2^>nul') do set "CTX_ORIG=%%u"
if "!CTX_ORIG!"=="" (
  echo   origin:        ^(not set — use option 3^)
) else (
  echo   origin:        !CTX_ORIG!
)
for /f "delims=" %%a in ('git -C "%PROJECT_ROOT%" config user.name 2^>nul') do set "CTX_UN=%%a"
for /f "delims=" %%a in ('git -C "%PROJECT_ROOT%" config user.email 2^>nul') do set "CTX_UE=%%a"
if "!CTX_UN!"=="" (
  echo   commit name:   ^(not set — option 7^)
) else (
  echo   commit name:   !CTX_UN!
)
if "!CTX_UE!"=="" (
  echo   commit email:  ^(not set — option 7^)
) else (
  echo   commit email:  !CTX_UE!
)
if exist "%PROJECT_ROOT%\.git\gh-credential-store" (
  echo   HTTPS token:   saved in this repo ^(for HTTPS only; option 11^)
) else (
  echo   HTTPS token:   not saved here ^(if HTTPS asks for a password, use option 11^)
)
exit /b 0

REM First ## [X.Y.Z] in CHANGELOG.md that is not [Unreleased] (Keep a Changelog).
:get_changelog_ver
set CHG_VER=
if not exist "%PROJECT_ROOT%\CHANGELOG.md" exit /b 0
for /f "tokens=2 delims=[]" %%a in ('findstr /R "^## \[" "%PROJECT_ROOT%\CHANGELOG.md" 2^>nul') do (
  if not "%%a"=="Unreleased" (
    if not defined CHG_VER set CHG_VER=%%a
  )
)
exit /b 0

:eof
echo Bye.
endlocal
exit /b 0
