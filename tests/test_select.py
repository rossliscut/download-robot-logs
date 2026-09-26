import unittest
from datetime import datetime

from download_robot_logs.select import (
    filter_rotated,
    loaded_map_stems,
    map_wanted,
    to_zip_rel,
)


class LayoutTest(unittest.TestCase):
    def test_resource_and_log_paths(self) -> None:
        self.assertEqual(
            to_zip_rel("/usr/local/etc/.SeerRobotics/rbk/resources/maps/a.smap"),
            "maps/a.smap",
        )
        self.assertEqual(
            to_zip_rel("/usr/local/etc/.SeerRobotics/rbk/diagnosis/log/robod/log/RobodPro_a.log"),
            "log/RobodPro_a.log",
        )
        self.assertEqual(
            to_zip_rel("/usr/local/etc/.SeerRobotics/rbk/diagnosis/log/d/x.d.log.zst"),
            "log/d/x.d.log.zst",
        )
        self.assertEqual(
            to_zip_rel("/usr/local/etc/.SeerRobotics/rbk/resources/patlogs/pat_2026-09-26_12-27-35.pat"),
            "log/patlogs/pat_2026-09-26_12-27-35.pat",
        )
        self.assertEqual(to_zip_rel("/var/log/syslog"), "log/syslog")

    def test_rotated_window_drops_previous_day(self) -> None:
        rels = [
            "log/patlogs/pat_2026-09-25_12-46-12.pat",
            "log/patlogs/pat_2026-09-26_12-27-35.pat",
            "log/patlogs/pat_2026-09-26_13-38-13.pat",
            "log/d/robokit_2026-09-25_12-16-30.29.d.log.zst",
            "log/d/robokit_2026-09-26_12-27-30.30.d.log.zst",
            "log/robokit_2026-09-25_11-54-24.1.log",
            "log/robokit_2026-09-26_12-27-23.0.log",
            "log/syslog",
            "models/robot.model",
        ]
        start = datetime(2026, 9, 26, 12, 27, 23)
        end = datetime(2026, 9, 26, 14, 27, 7)
        kept = set(filter_rotated(rels, start, end, end))
        self.assertIn("log/patlogs/pat_2026-09-26_12-27-35.pat", kept)
        self.assertIn("log/patlogs/pat_2026-09-26_13-38-13.pat", kept)
        self.assertIn("log/robokit_2026-09-26_12-27-23.0.log", kept)
        self.assertIn("log/syslog", kept)
        self.assertIn("models/robot.model", kept)
        self.assertNotIn("log/patlogs/pat_2026-09-25_12-46-12.pat", kept)
        self.assertNotIn("log/d/robokit_2026-09-25_12-16-30.29.d.log.zst", kept)
        self.assertNotIn("log/robokit_2026-09-25_11-54-24.1.log", kept)

    def test_active_log_started_before_window_is_kept(self) -> None:
        rels = [
            "log/robokit_2026-09-26_12-27-23.0.log",
            "log/patlogs/pat_2026-09-26_13-38-13.pat",
            "log/d/robokit_2026-09-26_14-31-16.20.d.log.zst",
            "log/d/robokit_2026-09-26_14-36-16.21.d.log.zst",
        ]
        start = datetime(2026, 9, 26, 14, 34, 56)
        end = datetime(2026, 9, 26, 15, 4, 56)
        kept = set(filter_rotated(rels, start, end, end))
        self.assertIn("log/robokit_2026-09-26_12-27-23.0.log", kept)
        self.assertIn("log/patlogs/pat_2026-09-26_13-38-13.pat", kept)
        self.assertIn("log/d/robokit_2026-09-26_14-31-16.20.d.log.zst", kept)
        self.assertIn("log/d/robokit_2026-09-26_14-36-16.21.d.log.zst", kept)

    def test_loaded_map_ignores_catalog(self) -> None:
        text = "\n".join(
            [
                "[addMapMD5][Exol3Dpoints_13August_V1.smap|abc]",
                "[smap][144|20260923133437402-3D]",
                "_currentMap|20260923133437402-3D",
                "[uploadMap][1049|map_name|ExolFairlife3DpointsAP_25sepv2|_currentMap|20260923133437402-3D]",
            ]
        )
        stems = loaded_map_stems(text)
        self.assertEqual(stems, {"20260923133437402-3D"})
        self.assertTrue(map_wanted("20260923133437402-3D.smap", stems))
        self.assertTrue(map_wanted("20260923133437402-3D.2dlh", stems))
        self.assertFalse(map_wanted("Exol3Dpoints_13August_V1.smap", stems))


if __name__ == "__main__":
    unittest.main()
