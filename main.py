#!/usr/bin/env python3
import sys
import os
import traceback
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from telegram_client import TelegramClient
from ui_login import LoginDialog
from ui_window import BlocklistWindow


class BlocklistApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.profx.telegram-blocklist")
        self.connect("activate", self.on_activate)
        self._client = TelegramClient()
        self._win = None

    def on_activate(self, app):
        if os.environ.get("TELEGRAM_BLOCKLIST_DEMO") == "1":
            self._client.init_client(12345, "mock_hash")
            self._show_main_window()
            return

        if self._client.load_config():
            self._client.init_client(
                self._client.load_config()["api_id"],
                self._client.load_config()["api_hash"],
            )
            try:
                if self._client.is_authorized():
                    self._show_main_window()
                    return
            except Exception as e:
                print(f"Auto-login failed: {e}", file=sys.stderr)
        self._show_login()

    def _show_login(self):
        self._login = LoginDialog(self, self._on_send_code, self._on_sign_in)
        self._login.present()

    def _on_send_code(self, api_id, api_hash, phone):
        self._phone = phone
        self._api_id = api_id
        self._api_hash = api_hash
        self._client.init_client(api_id, api_hash)
        future = self._client.send_code(phone)

        def on_done(fut):
            try:
                fut.result()
                self._login.show_code_entry()
            except Exception as e:
                self._login.show_error(str(e))

        future.add_done_callback(on_done)

    def _on_sign_in(self, code):
        future = self._client.sign_in(self._phone, code)

        def on_done(fut):
            try:
                fut.result()
                self._client.save_config(self._api_id, self._api_hash)
                self._login.show_success()
                self._show_main_window()
            except Exception as e:
                self._login.show_error(str(e))

        future.add_done_callback(on_done)

    def _show_main_window(self):
        self._win = BlocklistWindow(self, self._client)
        self._win.present()

    def switch_account(self):
        self._client.reset()
        if self._win:
            self._win.close()
            self._win = None
        self._show_login()

    def do_shutdown(self):
        self._client.reset()
        Adw.Application.do_shutdown(self)


def main():
    app = BlocklistApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    main()
