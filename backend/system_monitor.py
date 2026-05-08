import psutil
import datetime


def collect_system_stats() -> dict:
    stats = {
        "timestamp": datetime.datetime.now().isoformat(),
        "cpu": 0.0,
        "ram": 0.0,
        "ram_used": 0,
        "ram_total": 0,
        "battery": -1,
        "plugged": False,
        "net_sent": 0,
        "net_recv": 0,
    }
    try:
        stats["cpu"] = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        stats["ram"] = mem.percent
        stats["ram_used"] = mem.used // (1024 ** 3)
        stats["ram_total"] = mem.total // (1024 ** 3)

        battery = psutil.sensors_battery()
        if battery is not None:
            stats["battery"] = battery.percent
            stats["plugged"] = battery.power_plugged

        net = psutil.net_io_counters()
        stats["net_sent"] = net.bytes_sent
        stats["net_recv"] = net.bytes_recv
    except Exception:
        pass

    return stats
