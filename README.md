# Shadowrocket 全球自动优选（独立维护版）

上游：[Johnshall/Shadowrocket-ADBlock-Rules-Forever](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) (`release/lazy_group.conf`)，授权：CC BY-SA 4.0。感谢原作者。此项目为独立修改版，不代表上游维护者的官方建议。

## 功能

* `♻️ 全球自动优选` 使用 Shadowrocket 内置 `url-test`，对当前可见并匹配的节点按 300 秒间隔探测，`timeout=5`，`tolerance=80`。
* `🛟 故障回退` 提供单独可选的 `fallback` 策略组。
* `✈️ 手动选择` 保留人工指定的选择口。
* 国际默认规则指向全球自动优选，CN 的 GEOIP 仍然直连。
* AI、流媒体和地区分组保留，AI 可以手动切换到允许的地区。
* 不存任何私人机场订阅、密钥或者账号。已有订阅需要在手机 Shadowrocket 中单独导入。

## 重要限制

1. `url-test` 是延迟优选，低延迟不代表最大带宽。测试异步，不能承诺实时毫秒级故障切换；休眠后假连接也未必消失。
2. `fallback` 策略组独立存在，不会凭空增强 `url-test`。如需 Shadowrocket 客户端的「启用回退」，必须在手机实际开启并验证；不同版本 UI 可能有差异。
3. `policy-regex-filter` 依据节点备注动态筛选，可能误排除包含订阅提醒字眼的真实节点；客户端可见节点的范围及分组行为应在 iPhone 上检查。
4. 配置文件不包含代理节点，也不提供私人代理订阅。AI 有地域限制，需要自己在「AI」策略组里指定可用地区。
5. 保持上游 DNS、MITM 等配置段原状。导入不代表需要在 iOS 安装 HTTPS 解密证书；默认不要启用 HTTPS 解密。
6. GitHub Actions 拉取上游时校验基本配置结构并生成，校验失败不会发布新文件；客户端兼容性仍需要真实设备测试。

## 在 GitHub 启用

目标仓库：`Anke66666/shadowrocket-global-auto`，建议创建 `public` 空仓库，然后将本项目**解压后的全部文件和目录**提交到 `main`，不是上传 ZIP 压缩包本身。

将 GitHub Actions 设置为允许运行；如需要，授予 workflow `Read and write permissions`。打开 Actions > `Safe upstream sync` > `Run workflow`。首次执行成功后检查 `global-auto.conf` 是否刷新，以及 `UPSTREAM.json` 的 SHA。

**稳定配置链接**（仅在仓库存在、完成提交并验证能访问后有效）：

`https://raw.githubusercontent.com/Anke66666/shadowrocket-global-auto/main/global-auto.conf`

使用 GitHub Pages 需要另行在 GitHub Settings > Pages 中启用，单靠提交文件不会自动获得 Pages 地址。

## 本地检查

```bash
python -m unittest discover -s tests -v
python scripts/build.py
```

`python scripts/build.py` 从上游拉取当前配置，校验后覆盖 `global-auto.conf`。上游发生重大结构变化时会拒绝更新，不影响仓库里上次发布的文件。

## 在 iPhone 使用

在 Shadowrocket 中先保留现有配置，导入上述已验证的配置 URL；在「配置」模式使用。检查 `♻️ 全球自动优选` 是否包含你已有订阅的节点，并查看是否能自动测速。需要指定地区的 AI 服务，可单独在 `AI` 组改选 `美国节点`。真实设备功能未经过本仓库生成脚本验证。