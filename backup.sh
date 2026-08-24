#!/usr/bin/env bash
# BRM Territory Hub -- back up your data (Mac/Linux)
# Copies data/territory.db to data/backups/territory-YYYYMMDD-HHMMSS.db
set -e
cd "$(dirname "$0")"
mkdir -p data/backups
if [ ! -f "data/territory.db" ]; then
  echo "No data/territory.db found yet -- nothing to back up."
  exit 0
fi
STAMP=$(date +%Y%m%d-%H%M%S)
cp data/territory.db "data/backups/territory-$STAMP.db"
echo "Backed up to data/backups/territory-$STAMP.db"
