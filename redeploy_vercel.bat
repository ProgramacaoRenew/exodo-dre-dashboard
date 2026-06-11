@echo off
chcp 65001 >nul
echo Triggering Vercel redeploy via empty commit...
cd /d "%~dp0"
git commit --allow-empty -m "chore: trigger vercel deploy"
git push origin main
echo Done! Vercel will now deploy automatically.
pause
