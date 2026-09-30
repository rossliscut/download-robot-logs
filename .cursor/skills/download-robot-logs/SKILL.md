---
name: download-robot-logs
description: >-
  Download a SEER Roboshop-style Robokit debug package from a robot: API 5130
  on TCP 19208 lists files, API 5101 downloads each one, then pack a deflated
  robokit-Debug zip (log, maps, models, roboview, calibrations, scripts).
  从机器人下载 Roboshop 风格的调试包：TCP 19208 上用 5130 列文件、5101 逐个下载，
  再打成 deflate 的 robokit-Debug zip。Use when the user asks to 获取日志,
  下载日志, 导出调试包, fetch a robot log, or match a Roboshop debug zip.
---

# Download Robot Debug Package / 下载机器人调试包

A Roboshop `robokit-Debug-*.zip` is not one server-side zip. Roboshop lists files, downloads them one by one, and packs locally. Do the same. Logs alone are not the package: also take models, recognition files (`roboview`), calibrations, scripts, params, objects, and runtimes. For maps, read `robokit_*.log` first and download only the maps that log shows as loaded.

Roboshop 的 `robokit-Debug-*.zip` 不是机器人上现成的一个压缩包。它先列文件，再逐个下载，最后在本机打包。按同样的方式做。只下日志不够，还要带上模型、识别结果（`roboview`）、标定、脚本、参数、物体和运行时文件。地图要先读 `robokit_*.log`，只下载日志里实际加载过的。

Verified against `10.1.48.64` and `robokit-Debug-20260926133033.zip` on 2026-09-26.

已用 `10.1.48.64` 和 2026-09-26 的 `robokit-Debug-20260926133033.zip` 核对过。

## Run the CLI / 调用命令

When the user asks to download logs or a debug package, run this command. Do not reimplement the protocol in a one-off script.

用户要下载日志或调试包时，运行这条命令。不要再写一次性脚本去重做协议。

```text
download-robot-logs --host <ip>
download-robot-logs --host <ip> --last 10m
download-robot-logs --host <ip> --rds --last 30m
download-robot-logs --host <ip> --start "yyyy-MM-dd HH:MM:SS" --end "yyyy-MM-dd HH:MM:SS" --output <zip-or-dir>
```

Add `--rds` when the user asks for RDS / RDSCore logs, not a robot Robokit package. Same port 19208, same 5130 then 5101. The 5130 body also sends `"isAiLogAnalysis":false` and `"isDownloadLogOnly":false`. Zip name is `RDSCore-Debug-<timestamp>.zip`. Do not apply the Robokit map filter.

用户要的是 RDS / RDSCore 日志，不是机器人 Robokit 包时，加上 `--rds`。端口仍是 19208，仍是先 5130 再 5101。5130 的正文还要带 `"isAiLogAnalysis":false` 和 `"isDownloadLogOnly":false`。zip 名叫 `RDSCore-Debug-<时间戳>.zip`。不要套用 Robokit 的地图过滤。

Zip folders from the 2026-09-29 capture of `192.168.220.128`: `logs/` (RDS `Rds_*.log`), `log/` (core `rdscore_*.log` / `rdscore_*.log.gz`, `RobodPro_*.log`, `syslog`), `config/` (file name only, including files that live in `config/block/`), `script/`, `task/`, `rhcr/`, `scene/`, `models/` (keep `models/bak/`), `params/`, `db/`, `runtimes/`. `logs/` and `log/` are different directories. Hourly `Rds_*.log` and rotated `rdscore_*` stay only when their segment overlaps the window. If 5130 lists no `Rds_*.log`, list `/opt/.data/rds/logs` with 5100 and keep the overlapping files. Do not put local `Roboshop_*.log` into the zip.

这次 `192.168.220.128` 的包里，zip 根目录是：`logs/`（RDS 的 `Rds_*.log`）、`log/`（core 的 `rdscore_*.log` / `rdscore_*.log.gz`、`RobodPro_*.log`、`syslog`）、`config/`（只保留文件名，`config/block/` 里的文件也摊平到这里）、`script/`、`task/`、`rhcr/`、`scene/`、`models/`（保留 `models/bak/`）、`params/`、`db/`、`runtimes/`。`logs/` 和 `log/` 不是同一个目录。按小时切的 `Rds_*.log` 和滚动的 `rdscore_*` 只保留时间段相交的。5130 没有 `Rds_*.log` 时，用 5100 列 `/opt/.data/rds/logs`，再按窗口留下相交的文件。本机的 `Roboshop_*.log` 不要打进 zip。

Older Robod leaves rhcr out of the 5130 list. If no path contains `/rhcr/` or a `rhcr_` file, list `/opt/.data/rdscore/diagnosis/log` with 5100 and take the directory named `rhcr` (`file_path` when that entry has one). If the listing has no such directory, try `/opt/.data/rdscore/diagnosis/log/rhcr`, then the same two steps under `/opt/data/rdscore/diagnosis/log`. Keep `rhcr_*.log` and `rhcr_*.log.gz` whose segment overlaps the window. One file still open at download time covers the window even when its name is older. A missing directory is normal.

老版 Robod 的 5130 清单里经常没有 rhcr。路径里没有 `/rhcr/`、也没有 `rhcr_` 文件时，用 5100 列 `/opt/.data/rdscore/diagnosis/log`，取名为 `rhcr` 的目录（条目里有 `file_path` 就用它）。清单里没有这个目录时，再试 `/opt/.data/rdscore/diagnosis/log/rhcr`，然后对 `/opt/data/rdscore/diagnosis/log` 做同样的两步。只保留时间段和窗口相交的 `rhcr_*.log`、`rhcr_*.log.gz`。下载时还没切走的那一份，文件名即使更早也算盖住窗口。目录不存在是正常的。

When the user asks for a recent span (最近 10 分钟, last half hour), pass `--last` and do not compute the window from this computer's clock. `--last 10m` means ten minutes; a bare number is minutes (`--last 10`), and `1h` / `90s` / `0:10:00` also work. `--Last` is the same flag. The tool asks the robot for its clock first (API **5117** `robot_core_datetime_req` → **15117**, empty body, `{"dateTime":"yyyy-MM-dd HH:mm:ss:mmm"}`), then the window ends at that time.

用户说最近一段时间（最近 10 分钟、最近半小时）时，传 `--last`，不要用这台电脑的时钟去算起止。`--last 10m` 是 10 分钟；只写数字就是分钟（`--last 10`），也可以写 `1h`、`90s`、`0:10:00`。`--Last` 是同一个参数。工具会先问机器人当前时间（API **5117** `robot_core_datetime_req` → **15117**，正文为空，返回 `{"dateTime":"yyyy-MM-dd HH:mm:ss:mmm"}`），窗口的结束时刻就是这个时间。

Pass `--start` and `--end` together only when the user named an absolute window. Do not combine them with `--last`. Otherwise omit all three. Robokit then uses the newest `robokit_*.log`. `--rds` uses the newest `rdscore_*.log`.

只有用户给了绝对起止时间才同时传 `--start` 和 `--end`。不要和 `--last` 一起用。都没说的话三个都不要传。Robokit 用最新一份 `robokit_*.log`。`--rds` 用最新一份 `rdscore_*.log`。

The tool is the public GitHub repo `rossliscut/download-robot-logs`:

- page: `https://github.com/rossliscut/download-robot-logs`
- clone URL: `https://github.com/rossliscut/download-robot-logs.git`

If `download-robot-logs --help` already works, use it. If the command is missing, clone that repo and install it, then run the command. Do not look for a machine-specific path such as `D:\workspace\...`. Anyone can clone the GitHub repo. The Cursor copy at `ross-li/download-robot-logs` is internal and is not the install source.

工具就是公开的 GitHub 仓库 `rossliscut/download-robot-logs`：

- 页面：`https://github.com/rossliscut/download-robot-logs`
- 克隆地址：`https://github.com/rossliscut/download-robot-logs.git`

`download-robot-logs --help` 能跑就直接用。命令不在时，克隆这个仓库并安装，然后再执行。不要去找某一台电脑上的路径，例如 `D:\workspace\...`。GitHub 上任何人都可以克隆。Cursor 上的 `ross-li/download-robot-logs` 是内部仓库，不要拿它当安装来源。

Install when the command is missing / 命令不在时这样安装：

1. `git clone https://github.com/rossliscut/download-robot-logs.git`
2. In the clone: `pip install -e .`
3. Run `download-robot-logs`. If it is still not on PATH, run `python -m download_robot_logs` from the clone.

1. 执行 `git clone https://github.com/rossliscut/download-robot-logs.git`。
2. 在克隆下来的目录里执行 `pip install -e .`。
3. 再运行 `download-robot-logs`。如果还不在 PATH 里，就在该目录执行 `python -m download_robot_logs`。

## Framing / 帧格式

TCP port **19208**. 16-byte header, multi-byte fields **big-endian**.

TCP 端口 **19208**。帧头 16 字节，多字节字段为**大端**。

| Offset / 偏移 | Size / 长度 | Field / 字段 |
|--------|------|--------|
| 0 | 1 | `0x5A` |
| 1 | 1 | `0x01` |
| 2 | u16 | sequence (`0` is fine) / 序号（填 `0` 即可） |
| 4 | u32 | body length / 正文长度 |
| 8 | u16 | API number / API 号 |
| 10 | 6 | Reserved. Send six `0x00` bytes. A response echoes the request API in the first two reserved bytes, then `00 00 00 02`. / 保留。请求填 6 个 `0x00`。响应前两字节回显请求 API，后面是 `00 00 00 02`。 |

Response API = request API + 10000. One response body is the whole payload, including multi-megabyte files. `length == 0` is an empty file, not a protocol error.

响应 API = 请求 API + 10000。一次响应的正文就是完整内容，包括几十 MB 的文件。`length == 0` 表示空文件，不是协议错误。

Not this flow: `19204` `1100/11100` (status) and `1500/11500` (model JSON).

不要走这条：`19204` 的 `1100/11100`（状态）和 `1500/11500`（模型 JSON）。

## 1. List — API 5130 / 列文件

`robot_core_get_debug_fileList_req` → **15130**.

```json
{"startTime":"2026-09-26 13:36:03","endTime":"2026-09-26 13:46:03"}
```

Response is `{"fileList":[{"dirName":"...","filePaths":["/abs/path", ...]}]}`. `filePaths` are absolute paths on the robot. Deduplicate them. The same `dirName` can repeat.

响应是 `{"fileList":[{"dirName":"...","filePaths":["/绝对路径", ...]}]}`。`filePaths` 是机器人上的绝对路径，要去重。同一个 `dirName` 可能出现多次。

Ask for the robot IP if it was not given. For a recent span, pass `--last` so the window is measured from the robot clock (5117), not from this computer. For an absolute window, pass `--start` and `--end`. If the user named neither, use the newest `robokit_*.log`. Do not widen the window across days.

没给机器人 IP 就先问。最近一段时间用 `--last`，按机器人自己的时钟（5117）往前算，不要用这台电脑的时间。绝对起止用 `--start` 和 `--end`。都没说就用最新一份 `robokit_*.log`。不要把窗口拉到跨天。

## Patlog when 5130 omits it / 清单里没有 patlog 时

Older Robod (RBK before the 25 series, such as 3.4.8) often leaves patlog out of the 5130 list. Newer Robod includes `.../diagnosis/log/patlogs/*.pat` in that list. After 5130, check the paths.

旧版 Robod（25 系列之前，例如 3.4.8）经常不在 5130 的清单里给出 patlog。新版会带上 `.../diagnosis/log/patlogs/*.pat`。拿到 5130 之后先看路径里有没有。

If any path contains `/patlogs/` or ends in `.pat`, the names are already known. Do not list the directory again. Still keep only the files whose segment overlaps the package time window, below. A 5130 list of every retained `.pat` is not a reason to download all of them. On 3.4.8 the robot keeps about 20 files, and a wide `startTime`/`endTime` returns that whole set.

路径里已经有 `/patlogs/` 或以 `.pat` 结尾时，名字就算知道了，不要再去列目录。即便如此，也只保留下面说的、时间段和调试包相交的文件。5130 把机器人上留着的 `.pat` 全列出来，不等于全下。3.4.8 大约只留 20 个文件，把 `startTime`/`endTime` 拉得很宽时，清单会把这 20 个都返回。

If none do, the list omitted them. List the directory with API **5100** `robot_core_filelist_req` → **15100**:

如果一条都没有，就是清单漏了。用 API **5100** `robot_core_filelist_req` → **15100** 去列目录：

```json
{"path":"/usr/local/etc/.SeerRobotics/rbk/diagnosis/log/patlogs"}
```

That directory is what Roboshop shows as `resources/patlogs`. The 15100 body is JSON. `file_list[].name` is the file name, `is_dir` says whether it is a directory, and `size` is KB. Download every entry that is not a directory and whose name ends with `.pat`, using 5101. Seen names are `pat_YYYY-MM-DD_HH-MM-SS.pat`; older notes also use `pat-YYYY-MM-DD-HH-mm-SS.pat`. Match the `.pat` suffix, not one spelling.

这个目录就是 Roboshop 里的 `resources/patlogs`。15100 的正文是 JSON。`file_list[].name` 是文件名，`is_dir` 表示是不是目录，`size` 单位是 KB。不是目录、且文件名以 `.pat` 结尾的，都用 5101 下载。见过的名字是 `pat_YYYY-MM-DD_HH-MM-SS.pat`；旧资料里也有 `pat-YYYY-MM-DD-HH-mm-SS.pat`。按 `.pat` 后缀匹配，不要卡死一种写法。

If 5100 says that directory is missing or returns an empty list, try `/usr/local/etc/.SeerRobotics/rbk/resources/patlogs` the same way. A missing directory is normal on a robot that has no patlog; continue the rest of the package.

如果 5100 表示目录不存在或列表为空，再用同样的方法试 `/usr/local/etc/.SeerRobotics/rbk/resources/patlogs`。机器人上本来就没有 patlog 时，目录不存在是正常的，其余文件照常下载。

Store every kept file as `log/patlogs/<name>`, including files that came from `resources/patlogs`.

留下的文件都存成 `log/patlogs/<文件名>`，包括从 `resources/patlogs` 找到的。

The package time window is the one the user asked for. A recent span (`--last`) ends at the robot clock from 5117 and starts that far before it. An absolute window uses `--start` and `--end` as given. If they did not give one, use the newest `robokit_*.log`: from the timestamp in that filename until the download time. Do not widen `startTime`/`endTime` across days just to make 5130 return resources. Resources come back either way. A wide window also returns every old rotated log, and that is what made the 14:27 package 450 MB instead of about 250 MB.

调试包的时间范围以用户指定的为准。最近一段时间（`--last`）的结束时刻是 5117 读到的机器人时间，开始时刻再往前推这段时长。绝对窗口就用给出的 `--start` 和 `--end`。用户没指定时，用最新的一份 `robokit_*.log`：从文件名里的时间到本次下载的时刻。不要为了让 5130 返回资源而把 `startTime`/`endTime` 拉到跨天。资源目录怎么样都会返回。窗口拉宽还会把旧的滚动日志整段带出来。14:27 那次包变成 450 MB 而不是大约 250 MB，就是这个原因。

Apply that window to every rotated log, not only `.pat`: `robokit_*.log`, `robokit_warning_*.log`, `robokit_error_*.log`, `trace/*.pft.zst`, `d/*.d.log.zst`, `RobodPro_*.log`, and `patlogs/*.pat`. A file covers the time from its filename timestamp until the next file in the same series (the newest runs until the download). Keep it when that span overlaps the window, including the file that was already open at the window start. Skip the previous file when it only continues for under a minute into the window. Files with no timestamp stay (`syslog`, `kern.log`, `crash.log`).

这个时间范围用在所有滚动日志上，不只是 `.pat`：`robokit_*.log`、`robokit_warning_*.log`、`robokit_error_*.log`、`trace/*.pft.zst`、`d/*.d.log.zst`、`RobodPro_*.log` 和 `patlogs/*.pat`。一段日志从文件名里的时间开始，到同系列下一个文件为止（最新的一段到下载时刻）。和窗口有重叠就保留，包括窗口开始时还没切走的那一份。上一段如果只多伸进窗口不到一分钟，就不要。没有时间戳的留下（`syslog`、`kern.log`、`crash.log`）。

On the 2026-09-26 14:27 download the current robokit log started at 12:27:23. Outside that window were 18 `.pat` files plus the 2026-09-25 `d/`, `trace/`, and `robokit_*.log` segments, about 215 MB after deflate.

2026-09-26 14:27 那次下载，当前 robokit 日志从 12:27:23 开始。窗口外有 18 个 `.pat`，以及 2026-09-25 的 `d/`、`trace/` 和 `robokit_*.log`，deflate 之后大约 215 MB。

## 2. Download — API 5101 / 下载单个文件

`robot_core_getfile_req` → **15101**. Split each absolute path into directory and file name.

把每条绝对路径拆成目录和文件名。

```json
{"path":"/usr/local/etc/.SeerRobotics/rbk/resources/maps","file_name":"Exol3Dpoints_17August_V1.2dlh"}
```

The 15101 body **is the file bytes** (no JSON wrapper). Write those bytes to the zip-relative path below.

15101 的正文**就是文件字节**（没有 JSON 包裹）。按下面的相对路径写入。

Download `robokit_*.log` before `maps/`. Read those logs, then download only the maps they show as loaded.

先下 `robokit_*.log`，再下 `maps/`。读完这些日志后，只下载其中实际加载过的地图。

## Maps: only the ones the robokit log loaded / 只下载日志里用过的地图

`maps/` is the bulk of the package (about 810 MB raw on the robot checked here, 37 files). Do not download the whole directory.

`maps/` 是包里最大的一块（这台机器人上原始大约 810 MB、37 个文件）。不要整目录都下。

After the plain-text `robokit_*.log`, `log/warning/*.log`, and `log/error/*.log` files are on disk, scan every one of them. The current map is named even when this segment has no load line. Collect the stem (the file name without `.smap` or `.2dlh`):

`robokit_*.log`、`log/warning/*.log`、`log/error/*.log` 都下到本地后全部扫一遍。这段日志没有重新加载地图时，里面仍然会写出当前地图。记下主干名（去掉 `.smap` 或 `.2dlh`）：

| Line / 日志行 | Example / 例子 | Stem / 主干名 |
|---------------|----------------|---------------|
| `[smap][144\|<stem>]` | `[smap][144\|20260923133437402-3D]` | `20260923133437402-3D` |
| `_currentMap\|<stem>` | `_currentMap\|20260923133437402-3D` | `20260923133437402-3D` |
| `[smap][644\|<stem> success` | `[smap][644\|20260923133437402-3D success, md5: ...]` | `20260923133437402-3D` |
| any `/maps/<stem>.smap` or `/maps/<stem>/...` | `.../maps/Exol3Dpoints_18September_RemoveDeadEnd/0.feature2d` | `Exol3Dpoints_18September_RemoveDeadEnd` |

From the 5130 list, download each `maps/` file whose name is `<stem>.smap`, `<stem>.2dlh`, or `<stem>.<other>`. A map in use has both the `.smap` and the `.2dlh`. On 7043 the 14:56 robokit segment had no load line; the warning log named `Exol3Dpoints_18September_RemoveDeadEnd`.

在 5130 的清单里，下载文件名是 `<主干名>.smap`、`<主干名>.2dlh` 或其他 `<主干名>.<后缀>` 的 `maps/` 文件。正在使用的地图要同时下 `.smap` 和 `.2dlh`。7043 在 14:56 切开的 robokit 分段里没有加载行，warning 日志写的是 `Exol3Dpoints_18September_RemoveDeadEnd`。

Ignore `[addMapMD5]`. That line registers `.smap` files present on the robot at startup, not the map the robot was running. Ignore `uploadMap` names while `_currentMap` stays on another map; those files were uploaded and not loaded. Do not skip `maps/` only because `[smap][144` is absent. If none of these three logs name a map, download every file under `maps/`.

不要把 `[addMapMD5]` 算进去。那一行只是启动时登记机器人上已有的 `.smap`，不是正在使用的地图。`uploadMap` 里的名字如果 `_currentMap` 仍是另一张地图，表示只上传了、没有加载，也不要下。不能因为没有 `[smap][144` 就跳过 `maps/`。这三类日志里都没有地图名时，把 `maps/` 里的文件全部下载。

## 3. Store like `robokit-Debug-*.zip` / 按调试包目录存放

Root folders / 根目录：`backupFile`, `calibrations`, `log`, `maps`, `models`, `objects`, `params`, `roboview`, `runtimes`, `scripts`.

| Robot path / 机器人路径 | In the package / 包内路径 |
|------------|----------------|
| `/usr/local/etc/.SeerRobotics/rbk/resources/<rest>` | `<rest>` (`maps/…`, `models/…`, `roboview/…`, …) |
| `.../diagnosis/log/<rest>` | `log/<rest>` |
| `.../diagnosis/log/robod/log/<file>` | `log/<file>` (flattened / 摊平) |
| `/var/log/<file>` | `log/<file>` |
| `/usr/local/SeerRobotics/robod/appInfo/log/<file>` | `log/<file>` |
| `.../robod/appInfo/backupFile/<file>` | `backupFile/<file>` |

`roboview/` is the recognition output (`source`, `debug` `.pcd`/`.jpg`, `CameraParam`, `DJI-mid360-TCP`). `maps/` holds `.2dlh` and `.smap`. `models/` holds `robot.model`, `robot.cp`, `safe.model`, and `bak/`.

`roboview/` 是识别结果（`source`、`debug` 的 `.pcd`/`.jpg`、`CameraParam`、`DJI-mid360-TCP`）。`maps/` 是 `.2dlh` 和 `.smap`。`models/` 是 `robot.model`、`robot.cp`、`safe.model` 以及 `bak/`。

`log/Roboshop_*.log` is written by Roboshop on the PC. It is not on the robot; do not try to download it.

`log/Roboshop_*.log` 是 Roboshop 写在电脑上的日志，机器人里没有，不要去下。

## 4. Zip / 打包

Pack the tree into `robokit-Debug-<timestamp>.zip` so log tools can open it the same way as a Roboshop export. Use **deflate** (`ZIP_DEFLATED`). A stored zip keeps the raw size (about 1.3 GB here); Roboshop's deflate of the same tree is about 250 MB, mostly because `maps/` and `roboview/` compress several times. Entries sit at the zip root (`maps/...`, `log/...`, `roboview/...`), not inside an extra folder. Include directory entries. Leave out the download log.

打成 `robokit-Debug-<时间戳>.zip`，让日志软件能按 Roboshop 导出包的方式打开。必须用 **deflate**（`ZIP_DEFLATED`）。不压缩的话这个目录大约 1.3 GB；同样内容经 Roboshop 压缩后大约 250 MB，主要是 `maps/` 和 `roboview/` 能压掉好几倍。条目放在 zip 根上（`maps/...`、`log/...`、`roboview/...`），不要再套一层目录。要写入目录项。不要把下载日志打进去。

## After download / 下载之后

Report the zip path, file count, and size per top folder. Analyzing an already-built debug zip is the `check-logs` skill. `.zst` members need decompressing before they can be read as text.

汇报 zip 路径、文件数，以及每个顶层目录的大小。分析已经打好的调试包用 `check-logs` 技能。`.zst` 要先解压才能当文本读。
