[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/mianyansanshengsanshi/file_backup)

# 目录级备份

***

## 简介：

	* 对选定目录进行多线程备份，并能在基础的完全备份基础上进行增量备份，方式类似RAW
	* 采用md5进行文件的差异分析，目前还没有引入对文件修改时间的分析
	* 目前只完成核心备份功能

## 所用环境:

	* ubuntu 18.04
	* python3.7.4
	* os
	* json
	* shutil
	* hashlib
	* threading

## TODO:

1. ~~根据文件的修改时间分析文件，简化分析流程，节省时间~~（完成）
2. 系统守护进程功能，间隔一段时间自动增量备份
3. 对多个源目录的支持，也是对核心功能的封装和改写（预计使用多进程）
4. GUI
