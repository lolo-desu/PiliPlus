from gi.repository import Adw, Gtk


def add_actions(window, item, box, body):
    if str(item["id"]).startswith("ss"):
        return
    liked = {"value": False}
    like = Gtk.Button(label="点赞")

    def toggle(*_):
        target = not liked["value"]
        like.set_sensitive(False)

        def done(_):
            liked["value"] = target
            like.set_label("取消赞" if target else "点赞")
            like.set_sensitive(True)

        window.async_call(
            lambda: window.service.like(item, target),
            done,
            lambda e: (like.set_sensitive(True), window.message(e)),
            scoped=False,
        )

    like.connect("clicked", toggle)
    box.append(like)

    def initial(value):
        liked["value"] = bool(value)
        like.set_label("取消赞" if value else "点赞")

    if not window.offline:
        window.async_call(
            lambda: window.service.request(
                "/x/web-interface/archive/has/like", {"bvid": item["id"]}
            ),
            initial,
            lambda _: None,
        )
    coins = Gtk.Button(label="投币")

    def coin(*_):
        dialog = Adw.AlertDialog(heading="为这个视频投币", body=item["title"])
        for key, title in [("cancel", "取消"), ("1", "投 1 枚"), ("2", "投 2 枚")]:
            dialog.add_response(key, title)
        dialog.set_close_response("cancel")
        dialog.connect(
            "response",
            lambda _, value: (
                window.async_call(
                    lambda: window.service.coin(item, int(value)),
                    lambda _: window.message("投币成功"),
                    scoped=False,
                )
                if value != "cancel"
                else None
            ),
        )
        dialog.present(window)

    coins.connect("clicked", coin)
    box.append(coins)
    fav = Gtk.Button(label="收藏到…")
    fav.connect("clicked", lambda *_: favorites(window, item))
    box.append(fav)
    comments = Gtk.Button(label="评论")
    comments.connect("clicked", lambda *_: show_comments(window, item))
    box.append(comments)


def favorites(window, item):
    def show(folders):
        dialog = Adw.Dialog(title="收藏到", content_width=450, content_height=500)
        toolbar = Adw.ToolbarView()
        bar = Adw.HeaderBar()
        toolbar.add_top_bar(bar)
        group = Adw.PreferencesGroup()
        rows = []
        for folder in folders:
            selected = bool(folder.get("fav_state"))
            row = Adw.SwitchRow(
                title=folder["title"], active=selected, use_markup=False
            )
            rows.append((folder["id"], selected, row))
            group.add(row)
        save = Gtk.Button(label="保存")
        save.add_css_class("suggested-action")

        def submit(*_):
            add = [
                identifier
                for identifier, old, row in rows
                if row.get_active() and not old
            ]
            remove = [
                identifier
                for identifier, old, row in rows
                if not row.get_active() and old
            ]
            if not add and not remove:
                dialog.close()
                return
            save.set_sensitive(False)
            window.async_call(
                lambda: window.service.set_favorites(item, add, remove),
                lambda _: (dialog.close(), window.message("已更新收藏")),
                lambda e: (save.set_sensitive(True), window.message(e)),
                scoped=False,
            )

        save.connect("clicked", submit)
        bar.pack_end(save)
        toolbar.set_content(Gtk.ScrolledWindow(child=group))
        dialog.set_child(toolbar)
        dialog.present(window)

    window.async_call(lambda: window.service.favorite_folders(item), show)


def show_comments(window, item):
    body = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=12,
        margin_top=18,
        margin_bottom=18,
        margin_start=18,
        margin_end=18,
    )
    window.push(
        "评论", Gtk.ScrolledWindow(child=Adw.Clamp(maximum_size=850, child=body))
    )
    editor = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, height_request=100)
    body.append(editor)
    send = Gtk.Button(label="发送评论", halign=Gtk.Align.END)
    send.add_css_class("suggested-action")
    body.append(send)
    group = Adw.PreferencesGroup(title="评论")
    body.append(group)

    def load(page=1):
        def show(comments):
            for comment in comments:
                row = Adw.ActionRow(
                    title=comment.get("member", {}).get("uname", ""),
                    subtitle=comment.get("content", {}).get("message", ""),
                    use_markup=False,
                )
                row.set_subtitle_lines(0)
                group.add(row)
            more.set_sensitive(bool(comments))
            more.page = page + 1

        window.async_call(lambda: window.service.comments(item, page), show)

    more = Gtk.Button(label="加载更多")
    more.page = 1
    more.connect("clicked", lambda *_: load(more.page))
    body.append(more)

    def submit(*_):
        buffer = editor.get_buffer()
        message = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        if not message.strip():
            return
        send.set_sensitive(False)
        window.async_call(
            lambda: window.service.send_comment(item, message),
            lambda _: (
                buffer.set_text(""),
                send.set_sensitive(True),
                window.message("评论已发送"),
            ),
            lambda e: (send.set_sensitive(True), window.message(e)),
            scoped=False,
        )

    send.connect("clicked", submit)
    load()


def remote_library(window):
    body = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=12,
        margin_top=18,
        margin_bottom=18,
        margin_start=18,
        margin_end=18,
    )
    window.push("Bilibili 收藏夹", Gtk.ScrolledWindow(child=body))

    def show(folders):
        group = Adw.PreferencesGroup()
        for folder in folders:
            row = Adw.ActionRow(
                title=folder["title"], activatable=True, use_markup=False
            )

            def open_folder(_, folder=folder):
                content = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL,
                    spacing=12,
                    margin_top=18,
                    margin_bottom=18,
                    margin_start=18,
                    margin_end=18,
                )
                window.push(folder["title"], Gtk.ScrolledWindow(child=content))
                more = Gtk.Button(label="加载更多")
                more.page = 1

                def load(*_):
                    more.set_sensitive(False)

                    def items(items):
                        window.cards(items, content)
                        more.page += 1
                        more.set_sensitive(bool(items))

                    window.async_call(
                        lambda: window.service.favorite_items(folder["id"], more.page),
                        items,
                        lambda e: (more.set_sensitive(True), window.message(e)),
                    )

                more.connect("clicked", load)
                content.append(more)
                load()

            row.connect("activated", open_folder)
            group.add(row)
        body.append(group)

    window.async_call(window.service.favorite_folders, show)
