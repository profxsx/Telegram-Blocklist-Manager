#!/usr/bin/env python3
import json
import os
from datetime import datetime
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, GObject


class BlockRow(Adw.ActionRow):
    __gsignals__ = {
        "toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, user):
        super().__init__()
        self._user = user
        self._checkbox = Gtk.CheckButton()
        self._checkbox.connect("toggled", self._on_toggled)
        self.add_prefix(self._checkbox)

        name = user["name"] or "Unknown"
        username = f" @{user['username']}" if user["username"] else ""
        self.set_title(f"{name}{username}")
        self.set_subtitle(f"ID: {user['id']}")

    def _on_toggled(self, btn):
        self.emit("toggled", btn.get_active())

    def get_user(self):
        return self._user

    def is_selected(self):
        return self._checkbox.get_active()

    def set_selected(self, val):
        self._checkbox.set_active(val)


class BlocklistWindow(Adw.ApplicationWindow):
    def __init__(self, app, telegram_client):
        super().__init__(application=app)
        self.set_title("Telegram Blocklist Manager")
        self.set_default_size(600, 500)
        self._client = telegram_client
        self._all_users = []

        # Use Adw.ToolbarView so the header bar enables proper window dragging
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        self._switch_btn = Gtk.Button(label="Switch Account")
        self._switch_btn.add_css_class("destructive-action")
        self._switch_btn.connect("clicked", self._on_switch_account)
        header.pack_start(self._switch_btn)

        toolbar_view.add_top_bar(header)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        search_entry = Gtk.SearchEntry(placeholder_text="Search by name, username, or ID...")
        search_entry.connect("search-changed", self._on_search)
        search_entry.set_halign(Gtk.Align.FILL)
        main_box.append(search_entry)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.set_filter_func(self._filter_func)
        self._search_text = ""

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(self._listbox)
        scrolled.set_vexpand(True)
        main_box.append(scrolled)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        self._reload_btn = Gtk.Button(label="Reload")
        self._reload_btn.add_css_class("suggested-action")
        self._reload_btn.connect("clicked", self._on_reload)
        toolbar.append(self._reload_btn)

        self._export_btn = Gtk.Button(label="Export")
        self._export_btn.connect("clicked", self._on_export)
        toolbar.append(self._export_btn)

        self._import_btn = Gtk.Button(label="Import")
        self._import_btn.connect("clicked", self._on_import)
        toolbar.append(self._import_btn)

        self._unblock_sel_btn = Gtk.Button(label="Unblock Selected")
        self._unblock_sel_btn.add_css_class("destructive-action")
        self._unblock_sel_btn.connect("clicked", self._on_unblock_selected)
        self._unblock_sel_btn.set_sensitive(False)
        toolbar.append(self._unblock_sel_btn)

        self._unblock_all_btn = Gtk.Button(label="Unblock All")
        self._unblock_all_btn.add_css_class("destructive-action")
        self._unblock_all_btn.connect("clicked", self._on_unblock_all)
        toolbar.append(self._unblock_all_btn)

        self._status_label = Gtk.Label(label="Loading...")
        self._status_label.set_halign(Gtk.Align.END)
        self._status_label.set_hexpand(True)
        toolbar.append(self._status_label)

        main_box.append(toolbar)
        toolbar_view.set_content(main_box)
        self.set_content(toolbar_view)

        self._client.connect("blocklist-loaded", self._on_blocklist_loaded)
        self._client.connect("operation-progress", self._on_progress)
        self._client.connect("operation-done", self._on_operation_done)
        self._client.connect("error", self._on_error)

        self._client.get_blocklist()

    def _on_switch_account(self, btn):
        app = self.get_application()
        if app:
            app.switch_account()

    def _on_reload(self, btn):
        self._status_label.set_text("Reloading...")
        self._client.get_blocklist()

    def _on_search(self, entry):
        self._search_text = entry.get_text().lower()
        self._listbox.invalidate_filter()

    def _filter_func(self, row):
        if not self._search_text:
            return True
        user = row.get_user()
        search_str = self._search_text
        return (
            search_str in (user["name"] or "").lower()
            or search_str in (user["username"] or "").lower()
            or search_str in str(user["id"])
        )

    def _on_blocklist_loaded(self, client, users):
        self._all_users = users

        def update_ui():
            while True:
                child = self._listbox.get_first_child()
                if child is None:
                    break
                self._listbox.remove(child)

            for user in users:
                row = BlockRow(user)
                row.connect("toggled", self._on_row_toggled)
                self._listbox.append(row)

            self._status_label.set_text(f"{len(users)} blocked")

        GLib.idle_add(update_ui)

    def _on_row_toggled(self, row, active):
        selected = sum(1 for r in self._get_rows() if r.is_selected())
        self._unblock_sel_btn.set_sensitive(selected > 0)
        self._status_label.set_text(
            f"{len(self._all_users)} blocked" + (f" — {selected} selected" if selected else "")
        )

    def _get_rows(self):
        rows = []
        child = self._listbox.get_first_child()
        while child is not None:
            rows.append(child)
            child = child.get_next_sibling()
        return rows

    def _on_unblock_selected(self, btn):
        selected = [r.get_user()["id"] for r in self._get_rows() if r.is_selected()]
        if not selected:
            return

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Unblock Users",
            body=f"Unblock {len(selected)} selected users?",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("unblock", "Unblock")
        dialog.set_response_appearance("unblock", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._do_unblock_selected, selected)
        dialog.present()

    def _do_unblock_selected(self, dialog, response, user_ids):
        if response == "unblock":
            self._unblock_sel_btn.set_sensitive(False)
            self._client.unblock(user_ids)

    def _on_unblock_all(self, btn):
        if not self._all_users:
            return

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Unblock All Users",
            body=f"This will unblock all {len(self._all_users)} blocked users. Type UNBLOCK to confirm.",
        )

        confirm_entry = Gtk.Entry(placeholder_text="Type UNBLOCK")
        dialog.set_extra_child(confirm_entry)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("unblock", "Unblock All")
        dialog.set_response_appearance("unblock", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._do_unblock_all, confirm_entry)
        dialog.present()

    def _do_unblock_all(self, dialog, response, confirm_entry):
        if response == "unblock":
            if confirm_entry.get_text().strip() != "UNBLOCK":
                return
            all_ids = [u["id"] for u in self._all_users]
            self._unblock_all_btn.set_sensitive(False)
            self._client.unblock(all_ids)

    def _on_progress(self, client, msg):
        GLib.idle_add(lambda: self._status_label.set_text(msg))

    def _on_operation_done(self, client, op):
        def refresh():
            self._all_users = []
            self._client.get_blocklist()
            self._unblock_sel_btn.set_sensitive(False)
            self._unblock_all_btn.set_sensitive(True)
        GLib.idle_add(refresh)

    def _on_error(self, client, msg):
        GLib.idle_add(lambda: self._status_label.set_text(f"Error: {msg}"))

    def _on_export(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Export Blocklist",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Save", Gtk.ResponseType.ACCEPT)

        json_filter = Gtk.FileFilter()
        json_filter.set_name("JSON files")
        json_filter.add_pattern("*.json")
        dialog.add_filter(json_filter)

        txt_filter = Gtk.FileFilter()
        txt_filter.set_name("Text files")
        txt_filter.add_pattern("*.txt")
        dialog.add_filter(txt_filter)

        default_name = f"blocklist_{datetime.now().strftime('%Y-%m-%d')}.json"
        dialog.set_current_name(default_name)

        dialog.connect("response", self._do_export)
        dialog.present()

    def _do_export(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        filepath = dialog.get_file().get_path()
        dialog.destroy()

        if filepath.endswith(".json"):
            data = [
                {"id": u["id"], "name": u["name"], "username": u["username"]}
                for u in self._all_users
            ]
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
        else:
            with open(filepath, "w") as f:
                for u in self._all_users:
                    f.write(f"{u['id']}\n")

    def _on_import(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Import Blocklist",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Open", Gtk.ResponseType.ACCEPT)

        json_filter = Gtk.FileFilter()
        json_filter.set_name("JSON files")
        json_filter.add_pattern("*.json")
        dialog.add_filter(json_filter)

        txt_filter = Gtk.FileFilter()
        txt_filter.set_name("Text files")
        txt_filter.add_pattern("*.txt")
        dialog.add_filter(txt_filter)

        dialog.connect("response", self._do_import)
        dialog.present()

    def _do_import(self, dialog, response):
        if response != Gtk.ResponseType.ACCEPT:
            return
        filepath = dialog.get_file().get_path()
        dialog.destroy()

        try:
            ids = []
            if filepath.endswith(".json"):
                with open(filepath) as f:
                    data = json.load(f)
                for entry in data:
                    ids.append(int(entry["id"]))
            else:
                with open(filepath) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            ids.append(int(line))
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return

        if not ids:
            return

        already_blocked = {u["id"] for u in self._all_users}
        overlap = [uid for uid in ids if uid in already_blocked]
        new_only = [uid for uid in ids if uid not in already_blocked]

        if not overlap:
            self._client.block(ids)
            return

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Users Already Blocked",
            body=f"{len(overlap)} of {len(ids)} users are already blocked:\n\n" +
                 "\n".join(str(uid) for uid in overlap[:10]) +
                 ("\n..." if len(overlap) > 10 else ""),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("skip", f"Block New Only ({len(new_only)})")
        dialog.add_response("all", f"Block All ({len(ids)})")
        dialog.set_response_appearance("all", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._do_import_after_check, ids, new_only)
        dialog.present()

    def _do_import_after_check(self, dialog, response, all_ids, new_only):
        if response == "cancel":
            return
        elif response == "skip":
            self._client.block(new_only)
        elif response == "all":
            self._client.block(all_ids)
