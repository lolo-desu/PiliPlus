# PiliPlus GTK4 原生迁移（未完成）

这是独立的 GTK4/libadwaita 原生前端，不加载 Flutter 引擎。**尚未达到原版全功能等价，不能替代原版。**

## 运行

NixOS：首次在本仓库运行 `nix-shell native/shell.nix --run native/build-core` 构建弹幕解码核心，然后运行 `native/run`。首次使用需要可用的 nixpkgs channel。核心直接复用上游生成的 Dart protobuf 类型。

常规 Linux 需要 Python 3.12+、PyGObject、GTK 4.12+、libadwaita 1.5+、WebKitGTK 6.0、libmpv、FFmpeg、libsecret 和 qrencode。安装依赖后运行 `native/run`。GTK 浅色/深色及导航由 libadwaita 渲染，无自制 Material 风格控件。

## 已接入的路径

- 原生自适应侧栏、搜索、详情、设置和文件对话框，系统浅色/深色。
- 本地收藏、历史、播放进度、原生资料库 JSON 导入导出。
- 原生弹幕叠加：滚动/顶部/底部弹幕、JSON/XML 导入、字体/透明度/显示区域/偏移/关键词屏蔽。高级 BAS 和弹幕发送尚未迁移。
- 内嵌 Gtk.GLArea + libmpv：播放、暂停、跳转、音量、倍速、全屏、外挂字幕、音轨切换、截图。
- FFmpeg 下载队列、取消、任务状态和离线播放；不支持断点恢复。
- Bilibili 推荐、热门、排行榜、搜索、详情、分 P、番剧时间表及 DASH 音视频分离播放；WBI 算法依据上游实现移植。动态目前只映射视频条目。
- 原生二维码登录、退出、远端收藏夹浏览、点赞/投币/收藏操作、评论读取与发送；账号写操作尚未进行真实账户验收。
- 在线分段弹幕，复用上游 protobuf 解码；原生画质/编码选择，记住偏好，切换保留进度与暂停状态。仅列出服务端当前实际返回的流。

“已接入”表示有实现路径，不等同于所有账号、源站、区域或硬件组合已经验证。网络错误会显示错误状态，不以空列表伪装成功。

## 尚未迁移或未完整验证

- QR 登录和互动的真实账号验收、密码登录、多账号/刷新、消息、关注、直播、完整动态和专栏。
- 完整弹幕/字幕自动发现、授权画质完整回归、投屏、画中画、缓存恢复、所有播放器手势和快捷键。
- 番剧授权/付费/地区限制、App API 与 gRPC 功能的完整回归。
- 原版 Hive 数据无损导入、原版设置全集、所有导航偏好及使用习惯的逐项对照。

完整的上游页面文件清单见 [feature-inventory.json](feature-inventory.json)。状态只有 partial/pending；没有把未做的项目标记为完成。原 Flutter 数据目录不会被打开或修改；原生版使用独立的 `$XDG_DATA_HOME/…-gtk` 目录。

## 验证

- `python3 -m unittest discover -s native/tests -p 'test_*.py'`：存储/协议/规则回归。
- `python3 native/tests/smoke.py`：真实 GTK 窗口、导航、收藏详情、设置弹窗与截图；支持 `NATIVE_TEST_WIDTH=460`、`NATIVE_TEST_DARK=1`。
- `python3 native/tests/player_smoke.py /path/to/640x360-test-video.mp4`：真实 GLArea + libmpv 解码、进度、暂停、跳转；可传第二个 AAC 音频文件参数，验证独立 HTTP 音轨。
- 真实公开 Bilibili DASH 在线视频已验证画面和双声道音轨；自动测试另用本地 HTTP 分离音轨防止 URL 被错误拆分。
- 本机 Wayland 上播放器测试通过。自动化不覆盖账号操作、所有在线播放源及完整易用性验收。

## 实现参考

- [libadwaita NavigationSplitView](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/class.NavigationSplitView.html)
- [GTK GLArea](https://docs.gtk.org/gtk4/class.GLArea.html)
- [mpv Render API](https://github.com/mpv-player/mpv/blob/master/include/mpv/render.h)

沿用本仓库上游许可证；原始 Dart 文件仍是其权威来源。
