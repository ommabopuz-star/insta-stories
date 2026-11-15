"""
Instagram istoriya avtomatikasi — @muhammadjon_texno
GitHub Actions har ~15 daqiqada `python bot.py` ni ishga tushiradi (bitta "tick").

Bitta tick:
  1) Telegram'dagi yangi bosishlar/buyruqlarni o'qiydi (✅ / ❌ / ⏭, /navbat, /hozir)
  2) Tasdiqlangan istoriyalarni Instagram'ga chiqaradi (faol soatlarda)
  3) Vaqt kelgan bo'lsa, navbatdagi istoriyani Telegram'ga tasdiq uchun yuboradi
  4) Instagram tokenini ~30 kunda bir yangilaydi

Maxfiy qiymatlar FAQAT muhit o'zgaruvchilarida (GitHub Secrets):
  TG_BOT_TOKEN, TG_CHAT_ID, IG_TOKEN, [IG_USER_ID], [GH_PAT]
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
STORIES = ROOT / "stories"
STATE_FILE = ROOT / "state.json"
CONFIG_FILE = ROOT / "config.json"

TG_API = "https://api.telegram.org/bot{token}/{method}"
IG_HOST = "https://graph.instagram.com"


# ───────────────────────── yordamchilar ─────────────────────────
def env(name: str, required: bool = True) -> str:
    v = os.environ.get(name, "").strip()
    if required and not v:
        sys.exit(f"[XATO] {name} muhit o'zgaruvchisi berilmagan (GitHub Secrets'ga qo'shing)")
    return v


def load_json(p: Path, default):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def save_json(p: Path, data) -> None:
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def log(msg: str) -> None:
    print(msg, flush=True)


class Clock:
    """Mahalliy vaqt (Toshkent UTC+5 standart)."""

    def __init__(self, cfg: dict, now_utc: datetime | None = None):
        self.tz = timezone(timedelta(hours=cfg.get("utc_offset_hours", 5)))
        self.now = (now_utc or datetime.now(timezone.utc)).astimezone(self.tz)

    def today(self) -> str:
        return self.now.strftime("%Y-%m-%d")

    def hm(self) -> str:
        return self.now.strftime("%H:%M")

    def iso(self) -> str:
        return self.now.isoformat(timespec="seconds")

    def local_date_of(self, iso: str | None) -> str | None:
        if not iso:
            return None
        return datetime.fromisoformat(iso).astimezone(self.tz).strftime("%Y-%m-%d")


# ───────────────────────── Telegram ─────────────────────────
class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = str(chat_id)

    def call(self, method: str, files=None, **params):
        url = TG_API.format(token=self.token, method=method)
        if files:
            data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items()}
            r = requests.post(url, data=data, files=files, timeout=60)
        else:
            r = requests.post(url, json=params, timeout=30)
        j = r.json()
        if not j.get("ok"):
            raise RuntimeError(f"Telegram {method} xato: {j.get('description')}")
        return j["result"]

    def send(self, text: str, markup=None):
        p = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
        if markup:
            p["reply_markup"] = markup
        return self.call("sendMessage", **p)

    def send_media(self, path: Path, caption: str, markup):
        is_video = path.suffix.lower() in (".mp4", ".mov")
        method, field = ("sendVideo", "video") if is_video else ("sendPhoto", "photo")
        with open(path, "rb") as f:
            return self.call(method, files={field: f}, chat_id=self.chat_id,
                             caption=caption, parse_mode="HTML", reply_markup=markup)

    def set_caption(self, message_id: int, caption: str):
        try:
            self.call("editMessageCaption", chat_id=self.chat_id, message_id=message_id,
                      caption=caption, parse_mode="HTML", reply_markup={"inline_keyboard": []})
        except RuntimeError as e:
            log(f"  (izohni yangilab bo'lmadi: {e})")

    def answer(self, cb_id: str, text: str):
        try:
            self.call("answerCallbackQuery", callback_query_id=cb_id, text=text)
        except RuntimeError:
            pass  # eski tugma — muhim emas


def keyboard(item_id: str):
    return {"inline_keyboard": [[
        {"text": "✅ Chiqar", "callback_data": f"ok:{item_id}"},
        {"text": "⏭ Keyinroq", "callback_data": f"skip:{item_id}"},
        {"text": "❌ Bekor", "callback_data": f"no:{item_id}"},
    ]]}


# ───────────────────────── Instagram ─────────────────────────
class Instagram:
    def __init__(self, token: str, user_id: str, version: str):
        self.token = token
        self.version = version
        self.user_id = user_id or self._me()

    def _url(self, path: str) -> str:
        return f"{IG_HOST}/{self.version}/{path}"

    @staticmethod
    def _check(r: requests.Response):
        j = r.json()
        if "error" in j:
            e = j["error"]
            raise RuntimeError(f"Instagram xato {e.get('code')}: {e.get('message')}")
        return j

    def _me(self) -> str:
        r = requests.get(self._url("me"), params={"fields": "user_id,username",
                                                  "access_token": self.token}, timeout=30)
        j = self._check(r)
        log(f"  Instagram akkaunt: @{j.get('username')} ({j.get('user_id')})")
        return str(j["user_id"])

    def publish_story(self, media_url: str, is_video: bool) -> str:
        params = {"media_type": "STORIES", "access_token": self.token}
        params["video_url" if is_video else "image_url"] = media_url
        c = self._check(requests.post(self._url(f"{self.user_id}/media"), data=params, timeout=60))
        cid = c["id"]
        # konteyner tayyor bo'lishini kutish (video uchun uzoqroq)
        for _ in range(40 if is_video else 12):
            s = self._check(requests.get(self._url(cid), params={
                "fields": "status_code,status", "access_token": self.token}, timeout=30))
            code = s.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Konteyner xatosi: {s.get('status')}")
            time.sleep(5)
        else:
            raise RuntimeError("Konteyner vaqtida tayyor bo'lmadi")
        p = self._check(requests.post(self._url(f"{self.user_id}/media_publish"),
                                      data={"creation_id": cid, "access_token": self.token}, timeout=60))
        return str(p["id"])

    def refresh_token(self) -> str:
        r = requests.get(f"{IG_HOST}/refresh_access_token", params={
            "grant_type": "ig_refresh_token", "access_token": self.token}, timeout=30)
        return self._check(r)["access_token"]


def update_github_secret(repo: str, pat: str, name: str, value: str) -> None:
    from nacl import encoding, public  # faqat kerak bo'lganda

    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    k = requests.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                     headers=h, timeout=30).json()
    box = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(value.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{repo}/actions/secrets/{name}", headers=h,
                     json={"encrypted_value": enc, "key_id": k["key_id"]}, timeout=30)
    if r.status_code not in (201, 204):
        raise RuntimeError(f"GitHub secret yangilanmadi: {r.status_code} {r.text[:200]}")


# ───────────────────────── navbat ─────────────────────────
def load_queue() -> dict[str, dict]:
    q = {}
    if not STORIES.exists():
        return q
    for d in sorted(STORIES.iterdir()):
        m = d / "meta.json"
        if d.is_dir() and m.exists():
            meta = load_json(m, {})
            meta["id"] = d.name
            meta["path"] = d / meta.get("media", "story.jpg")
            q[d.name] = meta
    return q


def item_state(state: dict, item_id: str) -> dict:
    return state["items"].setdefault(item_id, {"status": "pending", "skips": 0})


def next_pending(queue: dict, state: dict, clock: Clock):
    cands = []
    for iid, meta in queue.items():
        st = item_state(state, iid)
        if st["status"] != "pending":
            continue
        if meta.get("date") and meta["date"] > clock.today():
            continue
        if not meta["path"].exists():
            log(f"  [ogohlantirish] {iid}: fayl yo'q ({meta['path'].name})")
            continue
        cands.append((-int(meta.get("priority", 0)), st.get("skips", 0), iid))
    return queue[sorted(cands)[0][2]] if cands else None


TYPE_LABEL = {"fact": "💡 Texno-fakt", "poll": "📊 So'rovnoma", "reels": "🎬 Reels anonsi"}


def caption_for(meta: dict, extra: str = "") -> str:
    t = TYPE_LABEL.get(meta.get("type"), "📌 Istoriya")
    s = f"<b>{t}</b> · <code>{meta['id']}</code>"
    if meta.get("note"):
        s += f"\n{meta['note']}"
    if extra:
        s += f"\n\n{extra}"
    return s


def offer(tg: Telegram, meta: dict, state: dict, clock: Clock) -> None:
    msg = tg.send_media(meta["path"], caption_for(meta, "Instagram istoriyaga chiqaraymi?"),
                        keyboard(meta["id"]))
    st = item_state(state, meta["id"])
    st.update(status="offered", tg_msg=msg["message_id"], offered_at=clock.iso())
    daily = state.setdefault("offers_per_day", {})
    daily[clock.today()] = daily.get(clock.today(), 0) + 1
    for d in sorted(daily)[:-14]:  # eski kunlarni tozalash
        daily.pop(d)
    log(f"  → Telegram'ga yuborildi: {meta['id']}")


# ───────────────────────── asosiy tick ─────────────────────────
def handle_updates(tg: Telegram, queue: dict, state: dict, clock: Clock, owner_id: str) -> bool:
    """True qaytarsa — /hozir buyrug'i kelgan."""
    force = False
    ups = tg.call("getUpdates", offset=state.get("tg_offset", 0), timeout=0,
                  allowed_updates=["callback_query", "message"])
    for u in ups:
        state["tg_offset"] = u["update_id"] + 1
        if "callback_query" in u:
            cb = u["callback_query"]
            if str(cb["from"]["id"]) != owner_id:
                tg.answer(cb["id"], "Ruxsat yo'q")
                continue
            action, _, iid = cb.get("data", "").partition(":")
            if iid not in queue:
                tg.answer(cb["id"], "Bu istoriya topilmadi")
                continue
            st = item_state(state, iid)
            if st["status"] != "offered":
                tg.answer(cb["id"], f"Allaqachon: {st['status']}")
                continue
            if action == "ok":
                st.update(status="approved", decided_at=clock.iso())
                tg.answer(cb["id"], "Qabul qilindi, chiqarilmoqda…")
                log(f"  ✅ tasdiqlandi: {iid}")
            elif action == "no":
                st.update(status="rejected", decided_at=clock.iso())
                tg.answer(cb["id"], "Bekor qilindi")
                tg.set_caption(st["tg_msg"], caption_for(queue[iid], "❌ Bekor qilindi"))
                log(f"  ❌ bekor: {iid}")
            elif action == "skip":
                st.update(status="pending", skips=st.get("skips", 0) + 1)
                st.pop("offered_at", None)
                tg.answer(cb["id"], "Navbat oxiriga surildi")
                tg.set_caption(st["tg_msg"], caption_for(queue[iid], "⏭ Keyinroqqa surildi"))
                log(f"  ⏭ surildi: {iid}")
        elif "message" in u:
            m = u["message"]
            if str(m.get("from", {}).get("id")) != owner_id:
                continue
            text = (m.get("text") or "").strip().lower()
            if text.startswith("/navbat"):
                counts: dict[str, int] = {}
                for iid in queue:
                    s = item_state(state, iid)["status"]
                    counts[s] = counts.get(s, 0) + 1
                tg.send("📋 <b>Navbat holati</b>\n" + "\n".join(
                    f"• {k}: {v}" for k, v in sorted(counts.items())) or "Bo'sh")
            elif text.startswith("/hozir"):
                force = True
            elif text.startswith("/start") or text.startswith("/yordam"):
                tg.send("Salom! Men @muhammadjon_texno istoriya botiman.\n"
                        "/navbat — navbat holati\n/hozir — keyingi istoriyani hozir yuborish")
    return force


def in_active_hours(cfg: dict, clock: Clock) -> bool:
    start, end = cfg.get("active_hours", ["08:00", "23:00"])
    return start <= clock.hm() < end


def publish_approved(ig_factory, tg: Telegram, queue: dict, state: dict, clock: Clock,
                     cfg: dict, repo: str, branch: str) -> None:
    if not in_active_hours(cfg, clock):
        return
    for iid, st in state["items"].items():
        if st["status"] != "approved" or iid not in queue:
            continue
        meta = queue[iid]
        rel = meta["path"].relative_to(ROOT).as_posix()
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}"
        try:
            ig = ig_factory()
            media_id = ig.publish_story(url, meta["path"].suffix.lower() in (".mp4", ".mov"))
            st.update(status="published", published_at=clock.iso(), ig_media_id=media_id)
            tg.set_caption(st["tg_msg"], caption_for(meta, f"✅ Chiqdi · {clock.hm()}"))
            log(f"  📤 chiqarildi: {iid} → {media_id}")
        except Exception as e:  # noqa: BLE001
            st["errors"] = st.get("errors", 0) + 1
            log(f"  [XATO] {iid}: {e}")
            if st["errors"] >= 3:
                st["status"] = "failed"
                tg.send(f"⚠️ <code>{iid}</code> 3 marta chiqmadi va to'xtatildi.\n<i>{e}</i>")


def maybe_offer(tg: Telegram, queue: dict, state: dict, clock: Clock, cfg: dict, force: bool) -> None:
    if any(s["status"] == "offered" for s in state["items"].values()) and not force:
        return  # avvalgisiga javob kutilmoqda
    offered_today = state.get("offers_per_day", {}).get(clock.today(), 0)
    slots_passed = sum(1 for t in cfg.get("offer_times", []) if t <= clock.hm())
    allowed = min(slots_passed, cfg.get("max_per_day", 2))
    if not force and (offered_today >= allowed or not in_active_hours(cfg, clock)):
        return
    meta = next_pending(queue, state, clock)
    if meta:
        offer(tg, meta, state, clock)
        left = sum(1 for i in queue if item_state(state, i)["status"] == "pending")
        if left <= cfg.get("low_queue_warning", 3):
            tg.send(f"ℹ️ Navbatda {left} ta istoriya qoldi — yangi kontent tayyorlash vaqti.")
    elif force:
        tg.send("Navbat bo'sh — yangi istoriyalar qo'shilishi kerak.")


def maybe_refresh_token(state: dict, clock: Clock, tg: Telegram, ig_token: str, version: str) -> None:
    last = state.get("token_refreshed_at")
    if not last:
        state["token_refreshed_at"] = clock.iso()
        return
    age = clock.now - datetime.fromisoformat(last)
    if age < timedelta(days=30):
        return
    repo, pat = env("GITHUB_REPOSITORY", False), env("GH_PAT", False)
    if not pat:
        if age > timedelta(days=50) and not state.get("token_warned"):
            tg.send("⚠️ Instagram tokeni ~10 kunda eskiradi. GH_PAT qo'shilmagan, "
                    "shuning uchun uni qo'lda yangilang (README, 4-qadam).")
            state["token_warned"] = True
        return
    try:
        new = Instagram(ig_token, "x", version).refresh_token()
        update_github_secret(repo, pat, "IG_TOKEN", new)
        state["token_refreshed_at"] = clock.iso()
        state.pop("token_warned", None)
        log("  🔑 Instagram tokeni yangilandi")
    except Exception as e:  # noqa: BLE001
        log(f"  [XATO] token yangilanmadi: {e}")
        tg.send(f"⚠️ Instagram tokenini avtomatik yangilab bo'lmadi:\n<i>{e}</i>")


def main() -> None:
    cfg = load_json(CONFIG_FILE, {})
    state = load_json(STATE_FILE, {"tg_offset": 0, "items": {}})
    state.setdefault("items", {})
    clock = Clock(cfg)
    log(f"Tick: {clock.iso()}")

    tg = Telegram(env("TG_BOT_TOKEN"), env("TG_CHAT_ID"))
    ig_token = env("IG_TOKEN")
    version = cfg.get("ig_api_version", "v23.0")
    repo = env("GITHUB_REPOSITORY")
    branch = env("GITHUB_REF_NAME", False) or "main"

    _ig = {}

    def ig_factory():
        if "c" not in _ig:
            _ig["c"] = Instagram(ig_token, env("IG_USER_ID", False), version)
        return _ig["c"]

    queue = load_queue()
    for iid in queue:
        item_state(state, iid)

    force = handle_updates(tg, queue, state, clock, tg.chat_id)
    publish_approved(ig_factory, tg, queue, state, clock, cfg, repo, branch)
    maybe_offer(tg, queue, state, clock, cfg, force)
    maybe_refresh_token(state, clock, tg, ig_token, version)

    save_json(STATE_FILE, state)
    log("Tick tugadi.")


if __name__ == "__main__":
    main()
