# download-robot-logs

从仙工机器人（Robod，TCP 19208）下载一份和 Roboshop `robokit-Debug-*.zip` 相同结构的调试包。

没指定时间时，时间范围是最新一份 `robokit_*.log` 的开始时间到下载时刻。滚动日志（robokit、warning、error、trace、d、RobodPro、patlog）只保留和这个范围相交的分段。地图先读 Robokit 日志，只下载实际加载过的。最后用 deflate 打成 zip。

```text
download-robot-logs --host 10.1.48.64
download-robot-logs --host 10.1.48.64 --start "2026-09-26 12:27:23" --end "2026-09-26 14:27:07" --output D:\logs
```

`--start` 和 `--end` 要成对出现，格式是 `yyyy-MM-dd HH:MM:SS`。`--output` 可以是 zip 文件，也可以是目录。成功时把 zip 路径打到标准输出。

安装：

```text
pip install -e .
```

也可以不安装，在仓库里执行 `python -m download_robot_logs --host <ip>`。
