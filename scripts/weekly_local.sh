#!/bin/zsh
# Manual/fallback publish from this machine (full-fidelity Yahoo street
# EPS). The scheduled weekly publish normally runs in GitHub Actions via
# the private data store + NASDAQ incremental updates; use this when CI is
# down or you want an off-cycle refresh. Optional launchd scheduling:
#
#   cp scripts/com.groverburger.open8585.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.groverburger.open8585.plist
set -e
cd "$(dirname "$0")/.."

/opt/homebrew/bin/python3 scripts/publish.py

git add archive/
git diff --cached --quiet || git commit -m "Archive weekly screen $(date +%F)"
git pull --rebase origin master
git push

cd site
git init -q -b site
git add -A
git commit -q -m "Site build $(date +%F)"
git push --force git@github.com:groverburger/open8585.git site
cd ..
rm -rf site/.git
echo "published $(date)"
