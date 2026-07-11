#!/bin/zsh
# Weekly publish from this machine. Yahoo blocks GitHub's runner IPs on the
# street-EPS endpoint, so the scheduled run lives here, where the data is
# full-fidelity. Schedule with launchd (Friday 3:05 PM PT):
#
#   cp scripts/com.groverburger.open8585.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.groverburger.open8585.plist
#
# Logs to ~/Library/Logs/open8585.log (see plist). Remove with launchctl
# unload + delete the plist.
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
