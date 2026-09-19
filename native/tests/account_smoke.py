"""Exercise the native QR dialog using a fake passport, never a real account."""

import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk
from nativeapp.app import Application
from nativeapp.storage import Store

app = Application(Store("qr-test", tempfile.mkdtemp()), True)
errors = []
polls = []


def labels(widget):
    result = [widget.get_label()] if isinstance(widget, Gtk.Label) else []
    child = widget.get_first_child()
    while child:
        result.extend(labels(child))
        child = child.get_next_sibling()
    return result


def start():
    if not hasattr(app, "window") or app.window.get_width() <= 300:
        return True
    app.window.service.qr_generate = lambda: {
        "url": "https://example.org/fixture",
        "qrcode_key": "fixture",
    }

    def poll(key):
        assert key == "fixture"
        polls.append(key)
        return {"code": 86090 if len(polls) == 1 else 0}

    app.window.service.qr_poll = poll
    app.window.account()
    GLib.timeout_add(100, verify)
    return False


def verify():
    try:
        if len(polls) < 2 or "登录成功" not in labels(app.window.get_visible_dialog()):
            return True
        app.window.get_visible_dialog().close()
        GLib.timeout_add_seconds(3, finish)
    except Exception:
        errors.append(traceback.format_exc())
        app.quit()
    return False


def finish():
    if len(polls) != 2:
        errors.append("QR polling continued after success")
    print("Native QR rendering, scan confirmation and poll completion passed")
    app.window.close()
    app.quit()
    return False


GLib.timeout_add(500, start)
GLib.timeout_add_seconds(
    25, lambda: (errors.append("QR timeout"), app.quit(), False)[-1]
)
app.run(["native-account-test"])
if errors:
    raise RuntimeError("\n".join(errors))
