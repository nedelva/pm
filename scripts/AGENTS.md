# Scripts Guide

Start and stop scripts for the Docker Compose deployment. Each script changes to the project root and calls Docker Compose, so it can be run from any directory.

- `start.sh` (macOS, Linux): `docker compose up --build -d`.
- `stop.sh` (macOS, Linux): `docker compose down`.
- `start.ps1` (Windows PowerShell): same as `start.sh`.
- `stop.ps1` (Windows PowerShell): same as `stop.sh`.

Starting rebuilds the image, runs the app in the background at http://localhost:8000, and loads `.env` from the project root. SQLite data lives in the `project-management-data` named volume, which `docker compose down` keeps. Docker must be running.

Keep the scripts as thin wrappers around Docker Compose; configuration belongs in `docker-compose.yml` and `Dockerfile`.
