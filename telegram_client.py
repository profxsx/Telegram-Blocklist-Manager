#!/usr/bin/env python3
import asyncio
import os
import threading
from telethon import TelegramClient as TelethonClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import GetBlockedRequest, UnblockRequest, BlockRequest
import gi

gi.require_version("GObject", "2.0")
from gi.repository import GObject


class TelegramClient(GObject.Object):
    __gsignals__ = {
        "connected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "disconnected": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "blocklist-loaded": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "operation-progress": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "operation-done": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self._client = None
        self._loop = None
        self._thread = None

    def _get_data_dir(self):
        data_dir = os.path.expanduser("~/.local/share/telegram-blocklist-manager")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _get_session_path(self):
        return os.path.join(self._get_data_dir(), "session")

    def _get_config_path(self):
        return os.path.join(self._get_data_dir(), "config.json")

    def save_config(self, api_id, api_hash):
        import json
        with open(self._get_config_path(), "w") as f:
            json.dump({"api_id": api_id, "api_hash": api_hash}, f)

    def load_config(self):
        import json
        path = self._get_config_path()
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return None

    def init_client(self, api_id, api_hash):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._client = TelethonClient(self._get_session_path(), api_id, api_hash)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def send_code(self, phone):
        async def _send():
            await self._client.connect()
            await self._client.send_code_request(phone)
            self.emit("connected")
        return asyncio.run_coroutine_threadsafe(_send(), self._loop)

    def sign_in(self, phone, code):
        async def _sign():
            await self._client.sign_in(phone, code)
            self.emit("connected")
        return asyncio.run_coroutine_threadsafe(_sign(), self._loop)

    def is_authorized(self):
        if not self._client or not self._loop:
            return False
        async def _check():
            await self._client.connect()
            return await self._client.is_user_authorized()
        try:
            future = asyncio.run_coroutine_threadsafe(_check(), self._loop)
            return future.result(timeout=15)
        except Exception:
            return False

    def get_blocklist(self):
        async def _get():
            all_users = []
            offset = 0
            limit = 100
            while True:
                result = await self._client(GetBlockedRequest(offset=offset, limit=limit))
                for user in result.users:
                    all_users.append({
                        "id": user.id,
                        "name": getattr(user, "first_name", "") or "",
                        "username": getattr(user, "username", None),
                    })
                if len(result.users) < limit:
                    break
                offset += limit
                await asyncio.sleep(1)
            self.emit("blocklist-loaded", all_users)
            return all_users
        return asyncio.run_coroutine_threadsafe(_get(), self._loop)

    def unblock(self, user_ids):
        async def _unblock():
            for uid in user_ids:
                try:
                    await self._client(UnblockRequest(id=uid))
                    self.emit("operation-progress", f"Unblocked {uid}")
                except FloodWaitError as e:
                    self.emit("operation-progress", f"Waiting {e.seconds}s...")
                    await asyncio.sleep(e.seconds)
                    await self._client(UnblockRequest(id=uid))
            self.emit("operation-done", "unblock")
        return asyncio.run_coroutine_threadsafe(_unblock(), self._loop)

    def block(self, user_ids):
        async def _block():
            for uid in user_ids:
                try:
                    await self._client(BlockRequest(id=uid))
                    self.emit("operation-progress", f"Blocked {uid}")
                except FloodWaitError as e:
                    self.emit("operation-progress", f"Waiting {e.seconds}s...")
                    await asyncio.sleep(e.seconds)
                    await self._client(BlockRequest(id=uid))
            self.emit("operation-done", "block")
        return asyncio.run_coroutine_threadsafe(_block(), self._loop)

    def reset(self):
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)
        for path in [self._get_session_path() + ".session", self._get_config_path()]:
            if os.path.exists(path):
                os.remove(path)
        self._client = None
        self._loop = None
        self._thread = None
