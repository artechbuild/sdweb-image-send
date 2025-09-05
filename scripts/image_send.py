import os
import base64
import mimetypes
import threading
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from modules import script_callbacks, shared

DEBUG = False
def dprint(*args):
    if DEBUG:
        print("[image-post]", *args)

# ====== 設定項目 ======
# WebUIのSettingsに出すオプション
def on_ui_settings():
    section = ("image_send_info", "Image Send Info")
    shared.opts.add_option(
        "msforum_enable_image_save_integration",
        shared.OptionInfo(False, "Send all images", section=section)
    )
    shared.opts.add_option(
        "msforum_outside_server_url_port",
        shared.OptionInfo("", "Outside server base URL (e.g. https://example.com:8443)", section=section)
    )
    shared.opts.add_option(
        "msforum_save_to_folderid",
        shared.OptionInfo("", "FolderID", section=section)
    )
    shared.opts.add_option(
        "msforum_auth_token",
        shared.OptionInfo("", "Auth Token (optional, sent as X-Auth-Token)", section=section)
    )
    shared.opts.add_option(
        "msforum_request_timeout_sec",
        shared.OptionInfo(10, "Request timeout (seconds)", section=section)
    )
    shared.opts.add_option(
        "msforum_max_retries",
        shared.OptionInfo(3, "HTTP max retries on failure", section=section)
    )
    shared.opts.add_option(
        "msforum_add_from_url_path",
        shared.OptionInfo("/api", "API path (e.g. /api)", section=section)
    )

script_callbacks.on_ui_settings(on_ui_settings)

# ====== HTTPセッション(リトライ付き) ======
_session_lock = threading.Lock()
_session: Optional[requests.Session] = None

def get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            s = requests.Session()
            # 指数バックオフ付きリトライ
            retries = Retry(
                total=int(shared.opts.msforum_max_retries or 3),
                backoff_factor=0.6,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("POST", "GET")
            )
            adapter = HTTPAdapter(max_retries=retries)
            s.mount("http://", adapter)
            s.mount("https://", adapter)
            _session = s
        return _session

# ====== 画像→data URL 変換 ======
def to_data_url(fullpath: Path) -> Optional[str]:
    if not fullpath.exists():
        dprint("file not found:", str(fullpath))
        return None

    # 拡張子からMIME推定（不明ならpng扱い）
    mime, _ = mimetypes.guess_type(str(fullpath))
    if not mime or not mime.startswith("image/"):
        # WebUI出力はほぼ画像だが念のため
        mime = "image/png"

    try:
        with open(fullpath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        # 余計な空白は入れない
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        dprint("b64 encode failed:", e)
        return None

# ====== 送信ジョブ ======
def _post_image_job(fullpath: Path, filename_noext: str, folder_id: str, base_url: str, url_path: str, token: Optional[str], timeout_sec: int):
    try:
        data_url = to_data_url(fullpath)
        if not data_url:
            return

        api_url = base_url.rstrip("/") + url_path
        payload = {
            "url": data_url,
            "name": filename_noext,
            "folderId": folder_id
        }
        headers = {}
        if token:
            headers["X-Auth-Token"] = token

        dprint("POST ->", api_url, "name=", filename_noext)
        resp = get_session().post(api_url, json=payload, headers=headers, timeout=timeout_sec)
        dprint("status:", resp.status_code)
        # 必要ならレスポンスを検証し、失敗時ログ
        if resp.status_code >= 300:
            dprint("server returned error body:", resp.text[:300])
    except Exception as e:
        dprint("post failed:", e)

# ====== コールバック（非同期起動） ======
def on_image_saved(params: script_callbacks.ImageSaveParams):
    if not getattr(shared.opts, "msforum_enable_image_save_integration", False):
        return

    base_url = getattr(shared.opts, "msforum_outside_server_url_port", "") or ""
    folder_id = getattr(shared.opts, "msforum_save_to_folderid", "") or ""
    token = getattr(shared.opts, "msforum_auth_token", "") or ""
    timeout_sec = int(getattr(shared.opts, "msforum_request_timeout_sec", 10) or 10)
    url_path = getattr(shared.opts, "msforum_add_from_url_path", "") or ""

    # 必須設定チェック
    if not base_url or not folder_id:
        dprint("skipped: base_url or folder_id is empty")
        return

    # params.filename は通常フルパス
    fullpath = Path(params.filename)
    filename_noext = fullpath.stem

    # 送信はワーカースレッドで非同期に
    t = threading.Thread(
        target=_post_image_job,
        args=(fullpath, filename_noext, folder_id, base_url, url_path, token, timeout_sec),
        daemon=True
    )
    t.start()

# コールバック登録
script_callbacks.on_image_saved(on_image_saved)
