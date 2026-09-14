# gh-pro 中文说明

gh-pro 帮你盘点 GitHub 公开贡献，并筛选下一步值得处理的 Issue 和项目问答。它区分「页面已经颁发的成就」和「API 查到的贡献」，不会把 PR 数量直接当成奖章等级。

需要 Python 3.10 及以上，无运行时 Python 依赖。先试离线演示：

```sh
python3 -m gh_pro demo
```

盘点公开账号，把 `YOUR_USERNAME` 换成自己的用户名：

```sh
python3 -m gh_pro audit YOUR_USERNAME
```

如果已登录 GitHub CLI，可以加上 `--auth-gh` 使用现有认证。查询 Discussions 需要此选项。程序不保存 token，也不修改现有认证权限。

```sh
mkdir -p reports
python3 -m gh_pro discover --repo OWNER/REPO --auth-gh --format json --output reports/opportunities.json
python3 -m gh_pro plan reports/opportunities.json --minutes 45
```

`OWNER/REPO` 替换为想贡献的公开项目，可重复指定，最多 5 个。发现器返回有限样本；当前没有合适事项时会如实报告。投入时间是粗略估计，开始前还需检查讨论上下文和已关联的 PR。

所有命令支持 `--format json`、`--format markdown` 和 `--output PATH`；指定文件会覆盖该文件。`report` 可以离线将 JSON 报告转成 Markdown。个人报告默认留在本地，示例中的 `reports/` 已被 Git 忽略。

成就通过 `audit --baseline baseline.json` 导入人工核实记录，格式见英文 README。缺少记录时显示未知，不要求先录入才能使用。Stars 按单仓库统计；不会把账号收藏的其他仓库或多个仓库的 Star 相加。

v0.1 尚不统计全部共同署名与已采纳答案，不自动抓取奖章，不后台运行，也不会自动发送消息、合并 PR、采纳答案或赞助。它的作用是提高寻找和完成真实贡献的效率。

详细边界、安装及测试命令见 [英文说明](../README.md)。
