"""Unit and smoke tests for Speedometer core services, formatting, and persistence."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from speedometer_app.models import Settings, format_rate, format_total, format_watts
from speedometer_app.services import (
    NetworkSampler,
    PowerMetricsService,
    SettingsRepository,
    SystemMetricsService,
    TrafficHistoryRepository,
)


class FormattingTests(unittest.TestCase):
    def test_format_rate_auto_bits_and_bytes(self) -> None:
        self.assertEqual(format_rate(0, "Auto (bits/s)"), "0 bps")
        self.assertEqual(format_rate(125_000, "Auto (bits/s)"), "1.0 Mbps")
        self.assertEqual(format_rate(125_000, "Auto (Bytes/s)"), "125 KB/s")
        self.assertEqual(format_rate(1_500_000, "Fixed MB/s", precision=2), "1.50 MB/s")
        self.assertEqual(format_rate(1_250_000, "Fixed Mbps", precision=2), "10.00 Mbps")

    def test_format_total(self) -> None:
        self.assertEqual(format_total(512), "512 B")
        self.assertEqual(format_total(2048), "2.0 KB")
        self.assertEqual(format_total(5 * 1024 ** 3), "5.00 GB")

    def test_format_watts_strictly_wattage(self) -> None:
        self.assertEqual(format_watts(None), "-- W")
        self.assertEqual(format_watts(-5.0), "-- W")
        self.assertEqual(format_watts(14.37), "14.4 W")
        self.assertEqual(format_watts(105.6), "106 W")


class PersistenceTests(unittest.TestCase):
    def test_settings_repository_roundtrip_and_legacy_migration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "settings.json"
            cfg.write_text('{"unit_mode": "Bytes/s", "opacity": 0.1, "unknown_key": 123, "dock_to_taskbar": true, "skin": "Modern Card"}', encoding="utf-8")
            repo = SettingsRepository(cfg)
            loaded = repo.load()
            self.assertEqual(loaded.unit_mode, "Auto (Bytes/s)")
            self.assertEqual(loaded.opacity, 0.30)  # clamped
            self.assertEqual(loaded.skin, "Taskbar Strip")
            self.assertEqual(loaded.schema_version, 2)

            loaded.skin = "Detailed Dashboard"
            loaded.show_taskbar_window = True
            repo.save(loaded)
            reloaded = repo.load()
            self.assertEqual(reloaded.skin, "Detailed Dashboard")
            self.assertTrue(reloaded.show_taskbar_window)

    def test_traffic_history_repository_summary_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hist_file = Path(tmp) / "history.json"
            repo = TrafficHistoryRepository(hist_file)
            today = date.today()
            yesterday = today - timedelta(days=1)

            repo.add_bytes(1_000, 500, day=today)
            repo.add_bytes(2_000, 1_000, day=yesterday)
            repo.save()

            repo2 = TrafficHistoryRepository(hist_file)
            summary = repo2.summary()
            self.assertEqual(summary["today"], (1_000, 500))
            self.assertEqual(summary["yesterday"], (2_000, 1_000))
            self.assertEqual(summary["all_time"], (3_000, 1_500))

            csv_path = Path(tmp) / "export.csv"
            repo2.export_csv(csv_path)
            content = csv_path.read_text(encoding="utf-8")
            self.assertIn("Date,Download (Bytes),Upload (Bytes),Total (Bytes)", content)
            self.assertIn("1500", content)


class SamplerTests(unittest.TestCase):
    def test_sampler_delta_clamps_resets_and_accumulates(self) -> None:
        seq = [
            {"Wi-Fi": SimpleNamespace(bytes_recv=1000, bytes_sent=200)},
            {"Wi-Fi": SimpleNamespace(bytes_recv=3000, bytes_sent=700)},
            {"Wi-Fi": SimpleNamespace(bytes_recv=500, bytes_sent=100)},  # counter reset
        ]
        stats = {"Wi-Fi": SimpleNamespace(isup=True, speed=1000, mtu=1500)}

        with patch("speedometer_app.services.psutil.net_if_stats", return_value=stats), \
             patch("speedometer_app.services.psutil.net_io_counters", side_effect=seq):
            sampler = NetworkSampler("Wi-Fi")
            snap1, d1, u1 = sampler.sample()
            self.assertEqual((d1, u1), (2000, 500))
            self.assertEqual((snap1.session_download_bytes, snap1.session_upload_bytes), (2000, 500))

            snap2, d2, u2 = sampler.sample()
            self.assertEqual((d2, u2), (0, 0))
            self.assertEqual((snap2.session_download_bytes, snap2.session_upload_bytes), (2000, 500))

    def test_system_metrics_snapshot(self) -> None:
        snap = SystemMetricsService.sample()
        self.assertGreaterEqual(snap.cpu_percent, 0.0)
        self.assertGreaterEqual(snap.memory_percent, 0.0)
        self.assertGreater(snap.memory_total_gb, 0.0)

    def test_settings_apply_theme(self) -> None:
        s = Settings()
        s.apply_theme("Windows 11 Light")
        self.assertEqual(s.background, "#F7F9FC")
        self.assertEqual(s.download, "#087F5B")
        self.assertEqual(s.power, "#B45309")

    def test_power_metrics_service_battery_and_pdh(self) -> None:
        svc = PowerMetricsService()
        try:
            with patch.object(PowerMetricsService, "_battery_discharge_watts", return_value=18.5), \
                 patch.object(svc, "_ensure_pdh"), \
                 patch.object(svc, "_sum_handles_mw", return_value=0.0):
                self.assertAlmostEqual(svc.sample_watts() or 0.0, 18.5)
        finally:
            svc.close()


if __name__ == "__main__":
    unittest.main()
