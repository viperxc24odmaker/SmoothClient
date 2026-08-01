"""Account management: offline accounts (Java-compatible UUIDs) and Microsoft
accounts via the OAuth 2.0 device-code flow. Persisted to accounts.json."""
from __future__ import annotations
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Callable, Optional

from . import config
from .utils import http_post_json, http_get_json

Log = Optional[Callable[[str], None]]


# --------------------------------------------------------------------------- #
# Offline UUID (identical to Java's UUID.nameUUIDFromBytes)                    #
# --------------------------------------------------------------------------- #
def offline_uuid(username: str) -> str:
    data = ("OfflinePlayer:" + username).encode("utf-8")
    md5 = bytearray(hashlib.md5(data).digest())
    md5[6] = (md5[6] & 0x0F) | 0x30   # version 3
    md5[8] = (md5[8] & 0x3F) | 0x80   # RFC-4122 variant
    return str(uuid.UUID(bytes=bytes(md5)))


@dataclass
class Account:
    kind: str            # "offline" | "microsoft"
    username: str
    uuid: str
    access_token: str = "0"
    refresh_token: str = ""
    user_type: str = "legacy"
    expires_at: float = 0.0

    @property
    def undashed(self) -> str:
        return self.uuid.replace("-", "")


# --------------------------------------------------------------------------- #
# Store                                                                        #
# --------------------------------------------------------------------------- #
class AccountStore:
    def __init__(self):
        self.accounts: list[Account] = []
        self.selected: Optional[str] = None
        self.load()

    def load(self):
        if config.ACCOUNTS_FILE.exists():
            raw = json.loads(config.ACCOUNTS_FILE.read_text("utf-8"))
            self.accounts = [Account(**a) for a in raw.get("accounts", [])]
            self.selected = raw.get("selected")

    def save(self):
        config.ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.ACCOUNTS_FILE.write_text(json.dumps(
            {"accounts": [asdict(a) for a in self.accounts], "selected": self.selected},
            indent=2), "utf-8")

    def add(self, account: Account):
        self.accounts = [a for a in self.accounts if a.uuid != account.uuid]
        self.accounts.append(account)
        self.selected = account.uuid
        self.save()

    def remove(self, uuid_str: str):
        self.accounts = [a for a in self.accounts if a.uuid != uuid_str]
        if self.selected == uuid_str:
            self.selected = self.accounts[-1].uuid if self.accounts else None
        self.save()

    def get_selected(self) -> Optional[Account]:
        return next((a for a in self.accounts if a.uuid == self.selected), None)

    def add_offline(self, username: str) -> Account:
        acc = Account(kind="offline", username=username, uuid=offline_uuid(username),
                      access_token="0", user_type="legacy")
        self.add(acc)
        return acc


# --------------------------------------------------------------------------- #
# Microsoft device-code flow                                                   #
# --------------------------------------------------------------------------- #
def start_device_code() -> dict:
    """Returns {user_code, verification_uri, device_code, interval, expires_in}."""
    return http_post_json(config.MS_DEVICECODE_URL, form={
        "client_id": config.MS_CLIENT_ID,
        "scope": config.MS_SCOPE,
    })


def poll_for_token(device: dict, log: Log = None) -> dict:
    """Poll until the user finishes signing in; returns MS token payload."""
    interval = int(device.get("interval", 5))
    deadline = time.time() + int(device.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(interval)
        try:
            tok = http_post_json(config.MS_TOKEN_URL, form={
                "client_id": config.MS_CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device["device_code"],
            })
        except Exception:
            continue
        if "access_token" in tok:
            return tok
        err = tok.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        raise RuntimeError(f"Microsoft sign-in failed: {err}")
    raise RuntimeError("Microsoft sign-in timed out.")


def _xbox_chain(ms_access_token: str) -> Account:
    # 1) Xbox Live
    xbl = http_post_json(config.XBL_AUTH_URL, payload={
        "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                       "RpsTicket": f"d={ms_access_token}"},
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT",
    })
    xbl_token = xbl["Token"]
    uhs = xbl["DisplayClaims"]["xui"][0]["uhs"]

    # 2) XSTS
    xsts = http_post_json(config.XSTS_AUTH_URL, payload={
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT",
    })
    xsts_token = xsts["Token"]

    # 3) Minecraft services token
    mc = http_post_json(config.MC_LOGIN_URL, payload={
        "identityToken": f"XBL3.0 x={uhs};{xsts_token}"
    })
    mc_token = mc["access_token"]

    # 4) Profile (uuid + name)
    profile = http_get_json(config.MC_PROFILE_URL,
                            headers={"Authorization": f"Bearer {mc_token}"})
    raw_id = profile["id"]
    dashed = str(uuid.UUID(raw_id)) if "-" not in raw_id else raw_id
    return Account(kind="microsoft", username=profile["name"], uuid=dashed,
                   access_token=mc_token, user_type="msa",
                   expires_at=time.time() + 86000)


def complete_microsoft(ms_token: dict, log: Log = None) -> Account:
    acc = _xbox_chain(ms_token["access_token"])
    acc.refresh_token = ms_token.get("refresh_token", "")
    if log:
        log(f"Signed in as {acc.username}")
    return acc
