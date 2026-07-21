#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class LoginDialog(Adw.ApplicationWindow):
    def __init__(self, app, on_send_code, on_sign_in):
        super().__init__(application=app, title="Login")
        self.set_default_size(400, 350)
        self._on_send_code = on_send_code
        self._on_sign_in = on_sign_in
        self._step = "credentials"

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        self._title = Gtk.Label(label="Telegram API Login")
        self._title.add_css_class("title-1")
        box.append(self._title)

        self._subtitle = Gtk.Label(label="Get API credentials from my.telegram.org")
        self._subtitle.add_css_class("dim-label")
        box.append(self._subtitle)

        self._api_id_entry = Gtk.Entry(placeholder_text="API ID (from my.telegram.org)")
        self._api_id_entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        box.append(self._api_id_entry)

        self._api_hash_entry = Gtk.Entry(placeholder_text="API Hash")
        self._api_hash_entry.set_visibility(False)
        box.append(self._api_hash_entry)

        self._phone_entry = Gtk.Entry(placeholder_text="Phone number (with country code, e.g. +1234567890)")
        self._phone_entry.set_input_purpose(Gtk.InputPurpose.PHONE)
        box.append(self._phone_entry)

        self._code_entry = Gtk.Entry(placeholder_text="Verification code from Telegram")
        self._code_entry.set_visible(False)
        box.append(self._code_entry)

        self._error_label = Gtk.Label(label="")
        self._error_label.add_css_class("error")
        self._error_label.set_visible(False)
        box.append(self._error_label)

        self._status_label = Gtk.Label(label="")
        self._status_label.add_css_class("dim-label")
        self._status_label.set_visible(False)
        box.append(self._status_label)

        self._action_btn = Gtk.Button(label="Send Code")
        self._action_btn.add_css_class("suggested-action")
        self._action_btn.connect("clicked", self._on_action)
        box.append(self._action_btn)

        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

    def _on_action(self, btn):
        if self._step == "credentials":
            api_id_text = self._api_id_entry.get_text().strip()
            api_hash = self._api_hash_entry.get_text().strip()
            phone = self._phone_entry.get_text().strip()

            if not api_id_text or not api_hash or not phone:
                self._show_error("All fields are required")
                return

            try:
                api_id = int(api_id_text)
            except ValueError:
                self._show_error("API ID must be a number")
                return

            self._api_id = api_id
            self._api_hash = api_hash
            self._phone = phone

            self._api_id_entry.set_sensitive(False)
            self._api_hash_entry.set_sensitive(False)
            self._phone_entry.set_sensitive(False)
            self._action_btn.set_sensitive(False)
            self._action_btn.set_label("Sending code...")
            self._show_status("Sending verification code to Telegram...")

            self._on_send_code(api_id, api_hash, phone)

        elif self._step == "code":
            code = self._code_entry.get_text().strip()
            if not code:
                self._show_error("Enter the code from Telegram")
                return

            self._action_btn.set_sensitive(False)
            self._action_btn.set_label("Signing in...")
            self._show_status("Signing in...")

            self._on_sign_in(code)

    def show_code_entry(self):
        def update():
            self._step = "code"
            self._code_entry.set_visible(True)
            self._action_btn.set_sensitive(True)
            self._action_btn.set_label("Login")
            self._title.set_label("Enter Verification Code")
            self._subtitle.set_label("Check Telegram for a message with your code")
            self._show_status("Code sent! Check your Telegram app.")
        from gi.repository import GLib
        GLib.idle_add(update)

    def show_success(self):
        from gi.repository import GLib
        GLib.idle_add(self.close)

    def show_error(self, msg):
        from gi.repository import GLib
        GLib.idle_add(self._show_error_impl, msg)

    def _show_error_impl(self, msg):
        self._show_error(msg)
        self._action_btn.set_sensitive(True)
        if self._step == "credentials":
            self._action_btn.set_label("Send Code")
        else:
            self._action_btn.set_label("Login")

    def _show_error(self, msg):
        self._error_label.set_text(msg)
        self._error_label.set_visible(True)

    def _show_status(self, msg):
        self._status_label.set_text(msg)
        self._status_label.set_visible(True)
