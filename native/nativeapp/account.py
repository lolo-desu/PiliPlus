import subprocess
from gi.repository import Adw, Gtk, GLib, Gdk


def show_account(window):
    dialog = Adw.Dialog(
        title="Bilibili 扫码登录", content_width=420, content_height=500
    )
    toolbar = Adw.ToolbarView()
    toolbar.add_top_bar(Adw.HeaderBar())
    box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=18,
        margin_top=24,
        margin_bottom=24,
        margin_start=24,
        margin_end=24,
    )
    picture = Gtk.Picture(can_shrink=True)
    picture.set_size_request(240, 240)
    box.append(picture)
    status = Gtk.Label(label="请使用哔哩哔哩手机客户端扫描", wrap=True)
    box.append(status)
    refresh = Gtk.Button(label="刷新二维码")
    box.append(refresh)
    logout = Gtk.Button(label="退出本机账号")
    box.append(logout)
    toolbar.set_content(box)
    dialog.set_child(toolbar)
    state = {"closed": False, "generation": 0}
    dialog.connect("closed", lambda *_: state.update(closed=True))

    def error(message):
        if not state["closed"]:
            status.set_text(str(message))
            refresh.set_sensitive(True)

    def generate(*_):
        state["generation"] += 1
        generation = state["generation"]
        refresh.set_sensitive(False)
        status.set_text("正在获取二维码…")

        def work():
            data = window.service.qr_generate()
            png = subprocess.run(
                ["qrencode", "-o", "-", "-t", "PNG", "-s", "6"],
                input=data["url"].encode(),
                capture_output=True,
                check=True,
                timeout=5,
            ).stdout
            return data["qrcode_key"], png

        def got(result):
            if state["closed"] or generation != state["generation"]:
                return
            key, png = result
            picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(png)))
            status.set_text("请使用哔哩哔哩手机客户端扫描")
            refresh.set_sensitive(True)

            def poll():
                if state["closed"] or generation != state["generation"]:
                    return False

                def polled(data):
                    if state["closed"] or generation != state["generation"]:
                        return
                    code = data["code"]
                    if code == 0:
                        status.set_text("登录成功")
                        picture.set_paintable(None)
                        window.message("Bilibili 登录成功")
                    elif code == 86038:
                        status.set_text("二维码已过期，请刷新")
                    elif code in (86101, 86090):
                        status.set_text(
                            "等待扫码" if code == 86101 else "已扫码，请在手机上确认"
                        )
                        GLib.timeout_add_seconds(2, poll)
                    else:
                        error(data.get("message", "登录失败"))

                window.async_call(
                    lambda: window.service.qr_poll(key), polled, error, scoped=False
                )
                return False

            GLib.timeout_add_seconds(2, poll)

        window.async_call(work, got, error, scoped=False)

    refresh.connect("clicked", generate)

    def signout(*_):
        state["generation"] += 1
        window.async_call(
            window.service.logout,
            lambda _: (picture.set_paintable(None), status.set_text("已退出本机账号")),
            error,
            scoped=False,
        )

    logout.connect("clicked", signout)
    dialog.present(window)
    generate()
