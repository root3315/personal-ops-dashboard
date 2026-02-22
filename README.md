# Personal Ops Dashboard

A lightweight CLI and cron-driven ops dashboard for personal monitoring and automation.

Collects CPU, memory, disk, network, load average, and process metrics. Supports configurable alert thresholds, service monitoring, historical summaries, and automated cron collection.

## Project Location

This project is located at `/tmp/personal-ops-dashboard_o_hkxwdj/` on the local filesystem. It is not currently pushed to a remote GitHub repository. The directory exists locally and contains all project files:

- `dashboard.py` - Main application script
- `requirements.txt` - Python dependencies
- `README.md` - This file

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Show current metrics
python dashboard.py now

# Start continuous monitoring
python dashboard.py monitor

# Run a health check
python dashboard.py health
```

## Commands

| Command | Description |
|---|---|
| `python dashboard.py now` | Display current system metrics |
| `python dashboard.py monitor [-i SECONDS]` | Continuous monitoring loop |
| `python dashboard.py collect` | Single snapshot (for cron) |
| `python dashboard.py history` | Historical summary from saved data |
| `python dashboard.py health` | One-shot health check with status |
| `python dashboard.py cron-install [-i MINUTES]` | Install a cron job for periodic collection |
| `python dashboard.py cron-remove` | Remove the dashboard cron job |
| `python dashboard.py config` | Show current configuration |
| `python dashboard.py config-set KEY VALUE` | Set a configuration value |
| `python dashboard.py services [NAME ...]` | Check if services are running |

## Configuration

Configuration lives in `~/.personal-ops-dashboard/config.json`. Defaults apply if the file is absent.

```json
{
  "thresholds": {
    "cpu_warn": 90,
    "memory_warn": 90,
    "disk_warn": 90
  },
  "services": ["nginx", "sshd", "docker"],
  "monitor_interval": 5,
  "cron_interval": 5
}
```

Set a value from the CLI:

```bash
python dashboard.py config-set thresholds.disk_warn 85
python dashboard.py config-set services '["nginx", "postgres"]'
```

## Cron Mode

Install a cron job to collect metrics every 5 minutes automatically:

```bash
python dashboard.py cron-install
```

Logs and collected data are stored under `~/.personal-ops-dashboard/`.

## Data Storage

| Path | Contents |
|---|---|
| `~/.personal-ops-dashboard/dashboard.log` | Activity and alert log |
| `~/.personal-ops-dashboard/history.json` | Collected metric snapshots (last 1000) |
| `~/.personal-ops-dashboard/config.json` | User configuration |
| `~/.personal-ops-dashboard/alerts.json` | Recent alert history |

## Requirements

- Python 3.7+
- psutil

## License

MIT
