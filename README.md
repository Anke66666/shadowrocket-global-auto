# Shadowrocket 全球自动优选（独立维护版）

上游：[Johnshall/Shadowrocket-ADBlock-Rules-Forever](https://github.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever) (`release/lazy_group.conf`)，授权：CC BY-SA 4.0。感谢原作者。此项目为独立修改版，不代表上游维护者的官方建议。

## 功能

* `♻️ 全球自动优选` 使用 Shadowrocket 内置 `url-test`，对当前可见并匹配的节点按 300 秒间隔探测，`timeout=5`，`tolerance=80`。
* `🛟 故障回退` 提供单独可选的 `fallback` 策略组。
* `✈️ 手动选择` 保留人工指定的选择口。
* 国际默认规则指向全球自动优选，CN 的 GEOIP 仍然直连。
* AI 和其他服务一样保留 `select` 分组，默认使用全球自动优选，可手动选择美国、日本、香港等地区；没有强制美国路由。
* 在 `[Rule]` 开头直接引用你原来的 [Gemini 增强规则 `.list`](https://github.com/Anke66666/gemini-shadowrocket-rules/blob/main/Gemini_2026_Shadowrocket.list)，策略设为 `AI`。和其他服务规则集保持相同用法，不展开域名，也不另存一份 Gemini 规则文件。
* 原有 AI 综合规则集继续保留，覆盖 ChatGPT、Claude、Copilot、Cursor、Grok、Perplexity 等服务；其他服务分组、国内直连和全球兜底策略保留。
* 不存任何私人机场订阅、密钥或者账号。已有订阅需要在手机 Shadowrocket 中单独导入。

## 重要限制

1. `url-test` 是延迟优选，低延迟不代表最大带宽。测试异步，不能承诺实时毫秒级故障切换；休眠后假连接也未必消失。
2. `fallback` 策略组独立存在，不会凭空增强 `url-test`。如需 Shadowrocket 客户端的「启用回退」，必须在手机实际开启并验证；不同版本 UI 可能有差异。
3. `policy-regex-filter` 依据节点备注动态筛选，可能误排除包含订阅提醒字眼的真实节点；客户端可见节点的范围及分组行为应在 iPhone 上检查。
4. 配置只筛选手机里已经导入且当前可见的节点，不会发现全世界的节点。AI 有地域限制，需要自己在 `AI` 策略组里指定可用地区。地区组按节点备注匹配，名称要匹配已有订阅里的实际节点；备注含“美国”也不证明真实出口位于美国。
5. 保持上游 DNS、MITM 等配置段原状。导入不代表需要在 iOS 安装 HTTPS 解密证书；默认不要启用 HTTPS 解密。
6. GitHub Actions 拉取上游时校验基本配置结构并生成，校验失败不会发布新文件；客户端兼容性仍需要真实设备测试。
7. Gemini 原规则中的 `apis.google.com`、`DOMAIN-KEYWORD,colab`、`developerprofiles` 等会匹配部分非 Gemini 流量。原 AI 综合规则集还包含整个 `googleapis.com`、`www.bing.com` 和部分 Apple 共用服务。选择 AI 策略时，这些匹配的共用服务也会跟随；本次保持这些既有规则范围，没有扩大成整个 `google.com`。
8. 本地测试只验证配置结构、规则顺序、节点名称匹配样例和同步失败保护。没有使用真实节点测速，没有在 iPhone 上验证故障切换、真实美国出口或 AI 服务解锁。启用的模块规则、旧连接和客户端保存的策略选择也可能影响实际结果。

## 配置链接

仓库：[Anke66666/shadowrocket-global-auto](https://github.com/Anke66666/shadowrocket-global-auto)。完整配置固定使用以下 Raw 链接，节点订阅仍保存在手机中：

`https://raw.githubusercontent.com/Anke66666/shadowrocket-global-auto/main/global-auto.conf`

使用 GitHub Pages 需要另行在 GitHub Settings > Pages 中启用，单靠提交文件不会自动获得 Pages 地址。

## 自动同步与来源记录

GitHub Actions 的 `Safe upstream sync` 每天北京时间 10:00 检查 Johnshall 完整配置和你的 Gemini 规则，也支持手动运行；GitHub 调度可能延迟。修改生成脚本、测试、配置或来源记录也会触发检查。

两份来源全部下载、校验并完成生成后，工作流再次运行测试，通过后才提交 `global-auto.conf` 和 `UPSTREAM.json`。下载失败、结构异常、规则缺少核心域名或测试失败时，本仓库中上次发布的版本保持原样。没有变化时不产生新提交。

完整配置使用这一条引用，位置在通用 Google、Microsoft、国内和 FINAL 规则之前：

```ini
RULE-SET,https://raw.githubusercontent.com/Anke66666/gemini-shadowrocket-rules/main/Gemini_2026_Shadowrocket.list,AI
```

`UPSTREAM.json` 仅记录构建时检查到的两个来源 URL、SHA256 及 Gemini 有效规则数，不保存额外的 Gemini 规则副本。生成器校验 `.list` 中的 `DOMAIN`、`DOMAIN-SUFFIX`、`DOMAIN-KEYWORD`，其他类型或内嵌策略会停止本仓库的自动发布，等待人工审查。

Shadowrocket 直接下载、缓存和刷新原 Gemini `.list`，其内容更新不必等待本仓库生成新配置。构建记录中的 SHA 只代表构建时读取的内容，不会锁定手机之后下载的版本；本仓库 CI 的校验也不会拦截原 Gemini 仓库之后的更新。完整配置本身有变动时，手机仍需更新配置。其他远程 `RULE-SET` 保持原状。

`tests/fixture_upstream.conf` 保留原 Johnshall 配置测试快照；历史正式版本保存在 Git 提交记录中。原 Gemini 仓库保持原样。两个来源的署名及规则来源链接均保留。

## 本地检查

```bash
python -m unittest discover -s tests -v
python scripts/build.py
```

`python scripts/build.py` 同时拉取两个来源，全部校验完成后生成文件。离线构建可以分别通过 `--source` 和 `--gemini-source` 指定本地输入文件；仓库的离线测试使用测试代码中的模拟规则，不依赖额外的 Gemini 规则文件。

测试包括原 `.list` 单次引用与优先顺序、AI 可选地区、全球策略保留、错误规则拒绝、来源失败保留旧文件、来源记录一致，以及离线重复生成。它们不模拟 Shadowrocket 的网络连接或故障切换。

## 在 iPhone 使用

先保留现有配置和节点订阅，更新或导入上述完整配置 URL，并在「配置」路由模式使用。AI 组默认和其他服务一样使用全球自动优选；你可以自行在 `AI` 组选择 `美国节点`。导入后如客户端保留了旧的策略选择，以手机当前显示为准。

美国组中应显示你订阅里实际存在的美国节点，再通过请求记录确认 Gemini 匹配 `AI` 并检查真实出口。没有匹配的美国节点时，该地区组没有可用候选；配置不会创建节点。全局测速与故障回退的实际表现仍需在手机检查。
