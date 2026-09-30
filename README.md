# download-robot-logs

从仙工机器人（Robod，TCP 19208）下载一份和 Roboshop `robokit-Debug-*.zip` 相同结构的调试包。

没指定时间时，时间范围是最新一份 `robokit_*.log` 的开始时间到下载时刻。滚动日志（robokit、warning、error、trace、d、RobodPro、patlog）只保留和这个范围相交的分段。地图先读 Robokit 日志，只下载实际加载过的。最后用 deflate 打成 zip。

```text
download-robot-logs --host 10.1.48.64
download-robot-logs --host 10.1.48.64 --last 10m
download-robot-logs --host 192.168.220.128 --rds --last 30m
download-robot-logs --host 10.1.48.64 --start "2026-09-26 12:27:23" --end "2026-09-26 14:27:07" --output D:\logs
```

`--last` 表示从机器人当前时间往前的一段时间，例如 `10m`、`1h`、`90s`，只写数字就是分钟。工具先用 API 5117 读取控制器时钟，再按这个时间计算窗口。`--rds` 下载 RDSCore 调试包（`logs/` 是 RDS 日志，`log/` 是 rdscore），默认文件名是 `RDSCore-Debug-<时间戳>.zip`。5130 没有 rhcr 时，会在 rdscore 的 diagnosis/log 下找 `rhcr` 目录，只下载和时间范围相交的 `rhcr_*.log`。`--start` 和 `--end` 要成对出现，格式是 `yyyy-MM-dd HH:MM:SS`，并且不能和 `--last` 一起用。`--output` 可以是 zip 文件，也可以是目录。成功时把 zip 路径打到标准输出。

安装：

```text
pip install -e .
```

也可以不安装，在仓库里执行 `python -m download_robot_logs --host <ip>`。
