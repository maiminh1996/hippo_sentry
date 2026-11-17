from hippo_sentry.system import SystemMonitor


def test_system_monitor():
    monitor = SystemMonitor()
    metrics = monitor.get_metrics()
    assert "cpu_percent" in metrics
    assert "app_ram_mb" in metrics
    assert "host_ram_gb" in metrics
    assert isinstance(metrics["cpu_percent"], float)
    assert isinstance(metrics["app_ram_mb"], float)
    assert isinstance(metrics["host_ram_gb"], float)
    assert metrics["host_ram_gb"] > 0
