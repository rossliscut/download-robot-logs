import unittest
from datetime import datetime, timedelta

from download_robot_logs.select import (
    chassis_map_stems,
    filter_rotated,
    listed_rhcr,
    listed_robokit,
    loaded_map_stems,
    map_wanted,
    parse_last,
    parse_robot_datetime,
    rhcr_dir_from_listing,
    rhcr_log_names,
    robokit_log_names,
    to_rds_zip_rel,
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

    def test_rds_zip_paths(self) -> None:
        self.assertEqual(
            to_rds_zip_rel("/opt/data/rds/config/block/BatchSettingSiteBp_en.json"),
            "config/BatchSettingSiteBp_en.json",
        )
        self.assertEqual(
            to_rds_zip_rel("/opt/data/rds/config/biz/SingleForkScene/taskList.task"),
            "config/taskList.task",
        )
        self.assertEqual(
            to_rds_zip_rel("/opt/.data/rdscore/resources/models/bak/20250912113414.robot.model"),
            "models/bak/20250912113414.robot.model",
        )
        self.assertEqual(
            to_rds_zip_rel("/opt/data/rds/history/task/7009Bench-1789427719296.task"),
            "task/7009Bench-1789427719296.task",
        )
        self.assertEqual(
            to_rds_zip_rel("/opt/.data/rds/logs/Rds_2026-09-29_10-00-00.log"),
            "logs/Rds_2026-09-29_10-00-00.log",
        )
        self.assertEqual(
            to_rds_zip_rel("/opt/.data/rdscore/diagnosis/log/rhcr/rhcr_2026-09-15_07-21-03_1.log"),
            "rhcr/rhcr_2026-09-15_07-21-03_1.log",
        )
        self.assertEqual(
            to_rds_zip_rel("/opt/.data/rdscore/diagnosis/log/rdscore_2026-09-29_10-36-01.78.log"),
            "log/rdscore_2026-09-29_10-36-01.78.log",
        )

    def test_rhcr_directory_comes_from_listing(self) -> None:
        parent = "/opt/.data/rdscore/diagnosis/log"
        self.assertFalse(listed_rhcr(["/opt/.data/rdscore/diagnosis/log/rdscore_2026-09-29_12-09-04.1.log"]))
        self.assertTrue(listed_rhcr([parent + "/rhcr/rhcr_2026-09-15_07-21-03_1.log"]))
        found = rhcr_dir_from_listing(
            parent,
            [
                {"name": "rdscore_2026-09-29_12-09-04.1.log", "is_dir": False},
                {"name": "rhcr", "is_dir": True, "file_path": parent + "/rhcr"},
            ],
        )
        self.assertEqual(found, parent + "/rhcr")
        built = rhcr_dir_from_listing(parent, [{"name": "rhcr", "is_dir": True}])
        self.assertEqual(built, parent + "/rhcr")
        self.assertIsNone(rhcr_dir_from_listing(parent, [{"name": "rhcr_old.log", "is_dir": False}]))
        self.assertEqual(
            rhcr_log_names(
                [
                    {"name": "rhcr_2026-09-15_07-21-03_1.log", "is_dir": False},
                    {"name": "notes.txt", "is_dir": False},
                    {"name": "rhcr", "is_dir": True},
                ]
            ),
            ["rhcr_2026-09-15_07-21-03_1.log"],
        )

    def test_rhcr_keeps_segment_that_covers_the_window(self) -> None:
        rels = [
            "rhcr/rhcr_2026-09-15_07-21-03_1.log",
            "rhcr/rhcr_2026-09-29_12-00-00_1.log",
            "rhcr/rhcr_2026-09-29_12-20-00_1.log",
        ]
        start = datetime(2026, 9, 29, 12, 10, 2)
        end = datetime(2026, 9, 29, 12, 15, 2)
        kept = set(filter_rotated(rels, start, end, end))
        self.assertNotIn("rhcr/rhcr_2026-09-15_07-21-03_1.log", kept)
        self.assertIn("rhcr/rhcr_2026-09-29_12-00-00_1.log", kept)
        self.assertNotIn("rhcr/rhcr_2026-09-29_12-20-00_1.log", kept)
        only = ["rhcr/rhcr_2026-09-15_07-21-03_1.log"]
        self.assertEqual(filter_rotated(only, start, end, end), only)

    def test_robokit_missing_from_5130_comes_from_listing(self) -> None:
        log = "/usr/local/etc/.SeerRobotics/rbk/diagnosis/log"
        listed = [
            log + "/warning/robokit_warning_2026-10-07_10-07-54.0.log",
            log + "/error/robokit_error_2026-10-07_10-07-51.0.log",
            log + "/trace/rbk+common_2026-10-07_11-26-35.pft.zst",
        ]
        self.assertFalse(listed_robokit(listed))
        self.assertTrue(listed_robokit(listed + [log + "/robokit_2026-10-07_11-21-02.10.log"]))
        names = robokit_log_names(
            [
                {"name": "warning", "is_dir": True},
                {"name": "robokit_2026-10-07_11-13-52.9.log", "is_dir": False},
                {"name": "robokit_2026-10-07_11-21-02.10.log", "is_dir": False},
            ]
        )
        self.assertEqual(
            names, ["robokit_2026-10-07_11-13-52.9.log", "robokit_2026-10-07_11-21-02.10.log"]
        )
        rels = ["log/" + name for name in names]
        start = datetime(2026, 10, 7, 11, 24, 34)
        end = datetime(2026, 10, 7, 11, 26, 34)
        self.assertEqual(filter_rotated(rels, start, end, end), ["log/robokit_2026-10-07_11-21-02.10.log"])

    def test_rds_hour_log_outside_window_is_dropped(self) -> None:
        rels = [
            "logs/Rds_2026-09-29_09-00-00.log",
            "logs/Rds_2026-09-29_10-00-00.log",
            "config/rbk-scripts.json",
        ]
        start = datetime(2026, 9, 29, 10, 10, 45)
        end = datetime(2026, 9, 29, 10, 40, 45)
        kept = set(filter_rotated(rels, start, end, end))
        self.assertNotIn("logs/Rds_2026-09-29_09-00-00.log", kept)
        self.assertIn("logs/Rds_2026-09-29_10-00-00.log", kept)
        self.assertIn("config/rbk-scripts.json", kept)

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

    def test_warning_path_names_current_map_without_load_line(self) -> None:
        text = (
            "[smap][256|map not found|/usr/local/etc/.SeerRobotics/rbk///"
            "private/shared/maps/Exol3Dpoints_18September_RemoveDeadEnd/0.feature2d]"
        )
        stems = loaded_map_stems(text)
        self.assertEqual(stems, {"Exol3Dpoints_18September_RemoveDeadEnd"})

    def test_chassis_info_names_current_map(self) -> None:
        text = "\n".join(
            [
                '[261007 112821.359][4866069][R][d] [Text][Chassis Info: {"AXISTRANSLATION":[1.0,0.0,0.0],'
                '"CURRENT_MAP":"MAP_Rialto_Aug_8","CURRENT_MAP_DETAILS":{"mapName":"MAP_Rialto_Aug_8"},'
                '"debug:current_map":"MAP_Rialto_Aug_8"}]',
                '[261007 100000.000][1][R][d] [Text][Chassis Info: {"CURRENT_MAP":"","debug:current_map":"old-3D"}]',
                '[261007 100000.000][1][R][d] [Text][Chassis Info: {"CURRENT_MAP":""}]',
                "[261007 100000.000][1][NP][i] [addMapMD5][other.smap|abc]",
                "[261007 100000.000][1][R][i] [smap][144|other]",
            ]
        )
        self.assertEqual(chassis_map_stems(text), {"MAP_Rialto_Aug_8", "old-3D"})
        self.assertEqual(chassis_map_stems("[smap][144|other]"), set())

    def test_robot_clock_drops_milliseconds(self) -> None:
        self.assertEqual(
            parse_robot_datetime('{"dateTime":"2026-09-26 13:21:02:601"}'),
            datetime(2026, 9, 26, 13, 21, 2),
        )

    def test_last_duration(self) -> None:
        self.assertEqual(parse_last("10"), timedelta(minutes=10))
        self.assertEqual(parse_last("10m"), timedelta(minutes=10))
        self.assertEqual(parse_last("1h"), timedelta(hours=1))
        self.assertEqual(parse_last("90s"), timedelta(seconds=90))
        self.assertEqual(parse_last("0:10:00"), timedelta(minutes=10))
        with self.assertRaises(ValueError):
            parse_last("0")


if __name__ == "__main__":
    unittest.main()
