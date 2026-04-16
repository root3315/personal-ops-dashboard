#!/usr/bin/env python3
"""
Personal Ops Dashboard - Lightweight CLI and cron-driven ops dashboard
for personal monitoring and automation.
"""

import os
import sys
import json
import time
import shutil
import signal
import socket
import argparse
import subprocess
import platform
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

try:
    import psutil
except ImportError:
    print("Installing dependency: psutil is required.")
    print("Run: pip install psutil")
    sys.exit(1)

# Constants
DASHBOARD_VERSION = "1.0.0"
DEFAULT_DATA_DIR = os.path.expanduser("~/.personal-ops-dashboard")
DEFAULT_LOG_FILE = os.path.join(DEFAULT_DATA_DIR, "dashboard.log")
DEFAULT_DB_FILE = os.path.join(DEFAULT_DATA_DIR, "history.json")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_DATA_DIR, "config.json")
DEFAULT_ALERT_FILE = os.path.join(DEFAULT_DATA_DIR, "alerts.json")

# Logging setup
os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(DEFAULT_LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("dashboard")


@dataclass
class SystemMetrics:
    """Container for a single snapshot of system metrics."""
    timestamp: str = ""
    hostname: str = ""
    cpu_percent: float = 0.0
    cpu_count: int = 0
    cpu_freq_mhz: float = 0.0
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_available_gb: float = 0.0
    memory_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_free_gb: float = 0.0
    disk_percent: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    load_avg_1: float = 0.0
    load_avg_5: float = 0.0
    load_avg_15: float = 0.0
    uptime_seconds: int = 0
    process_count: int = 0
    top_processes: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def get_system_metrics() -> SystemMetrics:
    """Collect current system metrics from psutil and OS APIs."""
    metrics = SystemMetrics()
    now = datetime.now()
    metrics.timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    metrics.hostname = socket.gethostname()

    # CPU
    metrics.cpu_percent = psutil.cpu_percent(interval=1)
    metrics.cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    if cpu_freq:
        metrics.cpu_freq_mhz = round(cpu_freq.current, 1)

    # Memory
    mem = psutil.virtual_memory()
    metrics.memory_total_gb = round(mem.total / (1024**3), 2)
    metrics.memory_used_gb = round(mem.used / (1024**3), 2)
    metrics.memory_available_gb = round(mem.available / (1024**3), 2)
    metrics.memory_percent = mem.percent

    # Disk (root partition)
    disk = shutil.disk_usage("/")
    metrics.disk_total_gb = round(disk.total / (1024**3), 2)
    metrics.disk_used_gb = round(disk.used / (1024**3), 2)
    metrics.disk_free_gb = round(disk.free / (1024**3), 2)
    metrics.disk_percent = round((disk.used / disk.total) * 100, 1)

    # Network
    net_io = psutil.net_io_counters()
    if net_io:
        metrics.network_bytes_sent = net_io.bytes_sent
        metrics.network_bytes_recv = net_io.bytes_recv

    # Load averages
    if hasattr(os, "getloadavg"):
        load1, load5, load15 = os.getloadavg()
        metrics.load_avg_1 = round(load1, 2)
        metrics.load_avg_5 = round(load5, 2)
        metrics.load_avg_15 = round(load15, 2)

    # Uptime
    boot_time = psutil.boot_time()
    metrics.uptime_seconds = int(time.time() - boot_time)

    # Process count
    metrics.process_count = len(psutil.pids())

    # Top 5 processes by CPU
    procs = []
    for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                    key=lambda x: x.info["cpu_percent"] or 0,
                    reverse=True)[:5]:
        procs.append({
            "pid": p.info["pid"],
            "name": p.info["name"] or "unknown",
            "cpu": p.info["cpu_percent"] or 0.0,
            "mem": p.info["memory_percent"] or 0.0,
        })
    metrics.top_processes = procs

    return metrics


def format_uptime(seconds: int) -> str:
    """Convert uptime in seconds to human-readable string."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable sizes."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def display_metrics(metrics: SystemMetrics):
    """Print formatted metrics to the terminal."""
    width = shutil.get_terminal_size().columns
    border = "=" * width
    thin_border = "-" * width

    print(f"\n{border}")
    print(f"  Personal Ops Dashboard v{DASHBOARD_VERSION}  |  {metrics.timestamp}")
    print(f"  Host: {metrics.hostname}  |  Uptime: {format_uptime(metrics.uptime_seconds)}")
    print(border)

    # CPU Section
    cpu_bar = _build_bar(metrics.cpu_percent, 30)
    print(f"\n  CPU [{cpu_bar}] {metrics.cpu_percent:.1f}%  ({metrics.cpu_count} cores, {metrics.cpu_freq_mhz} MHz)")
    print(f"  Load Average: {metrics.load_avg_1} / {metrics.load_avg_5} / {metrics.load_avg_15}")

    # Memory Section
    mem_bar = _build_bar(metrics.memory_percent, 30)
    print(f"  Memory [{mem_bar}] {metrics.memory_percent:.1f}%  ({metrics.memory_used_gb}/{metrics.memory_total_gb} GB)")

    # Disk Section
    disk_bar = _build_bar(metrics.disk_percent, 30)
    print(f"  Disk   [{disk_bar}] {metrics.disk_percent}%  ({metrics.disk_used_gb}/{metrics.disk_total_gb} GB, {metrics.disk_free_gb} free)")

    # Network
    print(f"\n  Network  TX: {format_bytes(metrics.network_bytes_sent)}  |  RX: {format_bytes(metrics.network_bytes_recv)}")
    print(f"  Processes: {metrics.process_count} running")

    # Top Processes
    if metrics.top_processes:
        print(f"\n{thin_border}")
        print(f"  {'PID':<8} {'NAME':<25} {'CPU%':<8} {'MEM%':<8}")
        print(f"  {thin_border}")
        for p in metrics.top_processes:
            print(f"  {p['pid']:<8} {p['name']:<25} {p['cpu']:<8.1f} {p['mem']:<8.1f}")

    print(f"\n{border}\n")


def _build_bar(percent: float, width: int) -> str:
    """Build an ASCII progress bar."""
    filled = int(width * min(percent, 100) / 100)
    bar = "#" * filled + "-" * (width - filled)
    return bar


def check_alerts(metrics: SystemMetrics, config: dict) -> list:
    """Evaluate thresholds from config and return any triggered alerts."""
    alerts = []
    thresholds = config.get("thresholds", {})

    cpu_warn = thresholds.get("cpu_warn", 90)
    if metrics.cpu_percent > cpu_warn:
        alerts.append(f"[ALERT] CPU usage high: {metrics.cpu_percent:.1f}% (threshold: {cpu_warn}%)")

    mem_warn = thresholds.get("memory_warn", 90)
    if metrics.memory_percent > mem_warn:
        alerts.append(f"[ALERT] Memory usage high: {metrics.memory_percent:.1f}% (threshold: {mem_warn}%)")

    disk_warn = thresholds.get("disk_warn", 90)
    if metrics.disk_percent > disk_warn:
        alerts.append(f"[ALERT] Disk usage high: {metrics.disk_percent}% (threshold: {disk_warn}%)")

    load_warn = thresholds.get("load_warn", metrics.cpu_count * 2)
    if metrics.load_avg_1 > load_warn:
        alerts.append(f"[ALERT] Load average high: {metrics.load_avg_1} (threshold: {load_warn})")

    return alerts


def save_snapshot(metrics: SystemMetrics, db_file: str):
    """Append a metrics snapshot to the history JSON file."""
    history = []
    if os.path.exists(db_file):
        try:
            with open(db_file, "r") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    history.append(metrics.to_dict())

    # Keep last 1000 entries to avoid unbounded growth
    max_entries = 1000
    if len(history) > max_entries:
        history = history[-max_entries:]

    with open(db_file, "w") as f:
        json.dump(history, f, indent=2)


def load_history(db_file: str) -> list:
    """Load historical metrics from the JSON database."""
    if not os.path.exists(db_file):
        return []
    try:
        with open(db_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def show_history_summary(history: list):
    """Print a summary of historical metrics."""
    if not history:
        print("No historical data available. Run the dashboard in monitor mode first.")
        return

    cpu_values = [h["cpu_percent"] for h in history if h.get("cpu_percent")]
    mem_values = [h["memory_percent"] for h in history if h.get("memory_percent")]
    disk_values = [h["disk_percent"] for h in history if h.get("disk_percent")]

    def stats(values):
        if not values:
            return {}
        return {
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "avg": round(sum(values) / len(values), 1),
            "samples": len(values),
        }

    print(f"\nHistorical Metrics Summary ({len(history)} snapshots)")
    print(f"  CPU:    min={stats(cpu_values).get('min')}%  max={stats(cpu_values).get('max')}%  avg={stats(cpu_values).get('avg')}%")
    print(f"  Memory: min={stats(mem_values).get('min')}%  max={stats(mem_values).get('max')}%  avg={stats(mem_values).get('avg')}%")
    print(f"  Disk:   min={stats(disk_values).get('min')}%  max={stats(disk_values).get('max')}%  avg={stats(disk_values).get('avg')}%")

    first_ts = history[0].get("timestamp", "unknown")
    last_ts = history[-1].get("timestamp", "unknown")
    print(f"  Range: {first_ts} -> {last_ts}\n")


def install_cron(interval_minutes: int = 5):
    """Install a cron entry that runs the dashboard collector."""
    script_path = os.path.abspath(__file__)
    python_path = sys.executable
    cron_line = f"*/{interval_minutes} * * * * {python_path} {script_path} --collect >> {DEFAULT_LOG_FILE} 2>&1"

    # Check if crontab is available
    result = subprocess.run(["which", "crontab"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Error: crontab is not available on this system.")
        print("Install cronie or vixie-cron, or use systemd timers instead.")
        return False

    # Read existing crontab
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing_lines = result.stdout if result.returncode == 0 else ""

    # Remove any existing dashboard cron entries
    lines = [l for l in existing_lines.strip().split("\n")
             if l.strip() and "personal-ops-dashboard" not in l and "--collect" not in l]

    lines.append(cron_line)
    new_crontab = "\n".join(lines) + "\n"

    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    if proc.returncode == 0:
        print(f"Cron job installed: runs every {interval_minutes} minutes")
        print(f"Command: {cron_line}")
        return True
    else:
        print("Failed to install cron job.")
        return False


def remove_cron():
    """Remove dashboard cron entries."""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        print("No crontab found.")
        return

    lines = [l for l in result.stdout.strip().split("\n")
             if l.strip() and "--collect" not in l]

    new_crontab = "\n".join(lines) + "\n" if lines else ""
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    print("Dashboard cron job removed.")


def check_services(services: list) -> list:
    """Check if specified services/processes are running."""
    results = []
    running_names = {p.info["name"] for p in psutil.process_iter(["name"])}
    for svc in services:
        found = any(svc.lower() in name.lower() for name in running_names)
        results.append({"name": svc, "running": found})
    return results


def monitor_loop(interval: int = 5, max_alerts: int = 50):
    """Run the dashboard in continuous monitoring mode."""
    logger.info("Starting dashboard monitor loop (interval=%ds)", interval)
    print(f"Dashboard monitor started (interval: {interval}s). Press Ctrl+C to stop.\n")

    alerts_log = []
    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False
        print("\nStopping dashboard monitor...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while running:
        try:
            metrics = get_system_metrics()
            display_metrics(metrics)
            save_snapshot(metrics, DEFAULT_DB_FILE)

            config = load_config()
            alerts = check_alerts(metrics, config)
            for alert in alerts:
                logger.warning(alert)
                print(f"  *** {alert}")
                alerts_log.append({"timestamp": metrics.timestamp, "alert": alert})
                if len(alerts_log) > max_alerts:
                    alerts_log = alerts_log[-max_alerts:]

            # Check configured services
            services = config.get("services", [])
            if services:
                svc_status = check_services(services)
                for svc in svc_status:
                    status_str = "RUNNING" if svc["running"] else "STOPPED"
                    if not svc["running"]:
                        logger.warning("Service %s is %s", svc["name"], status_str)
                    print(f"  Service: {svc['name']} -> {status_str}")

            # Write alerts to alert file
            if alerts_log:
                with open(DEFAULT_ALERT_FILE, "w") as f:
                    json.dump(alerts_log, f, indent=2)

        except Exception as e:
            logger.error("Error during monitor cycle: %s", e)

        # Sleep in small increments for responsive signal handling
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("Dashboard monitor loop stopped")
    print("Dashboard stopped.")


def load_config() -> dict:
    """Load configuration from the config file or return defaults."""
    default_config = {
        "thresholds": {
            "cpu_warn": 90,
            "memory_warn": 90,
            "disk_warn": 90,
            "load_warn": None,  # auto: cpu_count * 2
        },
        "services": [],
        "monitor_interval": 5,
        "cron_interval": 5,
    }

    if not os.path.exists(DEFAULT_CONFIG_FILE):
        logger.info("Config file not found at %s. Using defaults.", DEFAULT_CONFIG_FILE)
        return default_config

    try:
        with open(DEFAULT_CONFIG_FILE, "r") as f:
            user_config = json.load(f)
        # Merge with defaults
        for key, value in user_config.items():
            if isinstance(value, dict) and key in default_config:
                default_config[key].update(value)
            else:
                default_config[key] = value
    except json.JSONDecodeError as e:
        logger.error("Config file has invalid JSON: %s. Using defaults.", e)
    except IOError as e:
        logger.error("Could not read config file: %s. Using defaults.", e)

    return default_config


def save_config(config: dict):
    """Save configuration to the config file."""
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    logger.info("Configuration saved to %s", DEFAULT_CONFIG_FILE)


def run_health_check():
    """Run a one-shot health check and return status."""
    metrics = get_system_metrics()
    config = load_config()
    alerts = check_alerts(metrics, config)

    status = "HEALTHY"
    if alerts:
        status = "DEGRADED"

    result = {
        "status": status,
        "timestamp": metrics.timestamp,
        "hostname": metrics.hostname,
        "checks": {
            "cpu": {"value": metrics.cpu_percent, "ok": metrics.cpu_percent < config["thresholds"]["cpu_warn"]},
            "memory": {"value": metrics.memory_percent, "ok": metrics.memory_percent < config["thresholds"]["memory_warn"]},
            "disk": {"value": metrics.disk_percent, "ok": metrics.disk_percent < config["thresholds"]["disk_warn"]},
        },
        "alerts": alerts,
    }

    return result


def cmd_now(args):
    """Handler: show current metrics."""
    metrics = get_system_metrics()
    display_metrics(metrics)
    save_snapshot(metrics, DEFAULT_DB_FILE)
    logger.info("Snapshot saved")


def cmd_monitor(args):
    """Handler: start continuous monitoring."""
    interval = args.interval if args.interval else load_config().get("monitor_interval", 5)
    monitor_loop(interval=interval)


def cmd_collect(args):
    """Handler: collect a single snapshot (for cron)."""
    metrics = get_system_metrics()
    save_snapshot(metrics, DEFAULT_DB_FILE)

    config = load_config()
    alerts = check_alerts(metrics, config)
    for alert in alerts:
        logger.warning(alert)

    services = config.get("services", [])
    if services:
        svc_status = check_services(services)
        for svc in svc_status:
            if not svc["running"]:
                logger.warning("Service %s is STOPPED", svc["name"])

    logger.info("Collection complete")


def cmd_history(args):
    """Handler: show historical summary."""
    history = load_history(DEFAULT_DB_FILE)
    show_history_summary(history)


def cmd_health(args):
    """Handler: run health check."""
    result = run_health_check()
    status_icon = "OK" if result["status"] == "HEALTHY" else "!!"
    print(f"\nHealth Check: {status_icon} [{result['status']}]")
    print(f"  Timestamp: {result['timestamp']}")
    print(f"  Host: {result['hostname']}")
    for check_name, check_data in result["checks"].items():
        icon = "OK" if check_data["ok"] else "WARN"
        print(f"  {check_name}: {check_data['value']}% [{icon}]")
    if result["alerts"]:
        print(f"\n  Alerts ({len(result['alerts'])}):")
        for alert in result["alerts"]:
            print(f"    - {alert}")
    print()


def cmd_cron_install(args):
    """Handler: install cron job."""
    interval = args.interval if args.interval else load_config().get("cron_interval", 5)
    install_cron(interval)


def cmd_cron_remove(args):
    """Handler: remove cron job."""
    remove_cron()


def cmd_config(args):
    """Handler: show or edit configuration."""
    config = load_config()
    print(f"\nCurrent Configuration ({DEFAULT_CONFIG_FILE}):")
    print(json.dumps(config, indent=2))
    print()


def cmd_config_set(args):
    """Handler: set a configuration value."""
    config = load_config()
    key = args.key
    value = args.value

    # Try to parse value as number
    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            pass

    if "." in key:
        section, subkey = key.split(".", 1)
        if section not in config:
            config[section] = {}
        config[section][subkey] = value
    else:
        config[key] = value

    save_config(config)
    print(f"Set {key} = {value}")


def cmd_services(args):
    """Handler: check service status."""
    config = load_config()
    services = config.get("services", [])

    if args.service:
        services = args.service

    if not services:
        print("No services configured. Set them with: dashboard.py config-set services '[\"nginx\", \"ssh\"]'")
        return

    results = check_services(services)
    print(f"\nService Status:")
    for svc in results:
        icon = "RUNNING" if svc["running"] else "STOPPED"
        print(f"  {svc['name']:<25} {icon}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description=f"Personal Ops Dashboard v{DASHBOARD_VERSION} - System Monitoring & Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s now              Show current system metrics
  %(prog)s monitor          Start continuous monitoring
  %(prog)s collect          Collect single snapshot (for cron)
  %(prog)s history          Show historical summary
  %(prog)s health           Run health check
  %(prog)s cron-install     Install cron job for periodic collection
  %(prog)s cron-remove      Remove cron job
  %(prog)s config           Show current configuration
  %(prog)s config-set disk_warn 80  Set disk warning threshold
  %(prog)s services         Check status of configured services
        """,
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {DASHBOARD_VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # now
    p_now = subparsers.add_parser("now", help="Show current metrics")
    p_now.set_defaults(func=cmd_now)

    # monitor
    p_mon = subparsers.add_parser("monitor", help="Start continuous monitoring")
    p_mon.add_argument("-i", "--interval", type=int, help="Collection interval in seconds")
    p_mon.set_defaults(func=cmd_monitor)

    # collect
    p_col = subparsers.add_parser("collect", help="Collect single snapshot (for cron)")
    p_col.set_defaults(func=cmd_collect)

    # history
    p_hist = subparsers.add_parser("history", help="Show historical summary")
    p_hist.set_defaults(func=cmd_history)

    # health
    p_health = subparsers.add_parser("health", help="Run health check")
    p_health.set_defaults(func=cmd_health)

    # cron-install
    p_ci = subparsers.add_parser("cron-install", help="Install cron job")
    p_ci.add_argument("-i", "--interval", type=int, help="Cron interval in minutes")
    p_ci.set_defaults(func=cmd_cron_install)

    # cron-remove
    p_cr = subparsers.add_parser("cron-remove", help="Remove cron job")
    p_cr.set_defaults(func=cmd_cron_remove)

    # config
    p_conf = subparsers.add_parser("config", help="Show configuration")
    p_conf.set_defaults(func=cmd_config)

    # config-set
    p_cs = subparsers.add_parser("config-set", help="Set config value")
    p_cs.add_argument("key", help="Config key (e.g., thresholds.disk_warn)")
    p_cs.add_argument("value", help="Config value")
    p_cs.set_defaults(func=cmd_config_set)

    # services
    p_svc = subparsers.add_parser("services", help="Check service status")
    p_svc.add_argument("service", nargs="*", help="Service names to check")
    p_svc.set_defaults(func=cmd_services)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
