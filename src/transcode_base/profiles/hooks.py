"""Typed profiles for the notify and mail subsystems.

Mirrors `hooks.toml`:

    [smtp]
        host, user, password, to   strings
        port                       int
        use_starttls               bool

    [notification]
        app_name, icon, urgency, category   strings

    [notification.error]
        icon, urgency, category   strings  (inherits app_name from [notification])
"""

from __future__ import annotations

from attrs import frozen

from .base import RawProfile, get_int, get_str


@frozen
class _NotificationParams:
    app_name: str
    icon: str
    urgency: str
    category: str


@frozen
class NotifyProfile:
    normal: _NotificationParams
    error: _NotificationParams

    @classmethod
    def from_raw(cls, raw: RawProfile) -> NotifyProfile:
        section = raw.get("notification", {})
        if not isinstance(section, dict):
            msg = "hooks profile: 'notification' must be a table"
            raise ValueError(msg)
        error_raw = section.get("error", {})
        if not isinstance(error_raw, dict):
            msg = "hooks profile: 'notification.error' must be a table"
            raise ValueError(msg)
        app_name = get_str(section, "app_name", "notification")
        return cls(
            normal=_NotificationParams(
                app_name=app_name,
                icon=get_str(section, "icon", "notification"),
                urgency=get_str(section, "urgency", "notification"),
                category=get_str(section, "category", "notification"),
            ),
            error=_NotificationParams(
                app_name=app_name,
                icon=get_str(error_raw, "icon", "notification.error"),
                urgency=get_str(error_raw, "urgency", "notification.error"),
                category=get_str(error_raw, "category", "notification.error"),
            ),
        )

    @staticmethod
    def default_name() -> str:
        return "hooks"


@frozen
class MailProfile:
    host: str
    port: int
    user: str
    password: str
    to: str
    use_starttls: bool

    @classmethod
    def from_raw(cls, raw: RawProfile) -> MailProfile:
        section = raw.get("smtp", {})
        if not isinstance(section, dict):
            msg = "hooks profile: 'smtp' must be a table"
            raise ValueError(msg)
        use_starttls = section.get("use_starttls")
        if not isinstance(use_starttls, bool):
            actual = type(use_starttls).__name__ if use_starttls is not None else "missing"
            msg = f"hooks profile: smtp.use_starttls must be a bool, got {actual}"
            raise ValueError(msg)
        return cls(
            host=get_str(section, "host", "smtp"),
            port=get_int(section, "port", "smtp"),
            user=get_str(section, "user", "smtp"),
            password=get_str(section, "password", "smtp"),
            to=get_str(section, "to", "smtp"),
            use_starttls=use_starttls,
        )

    @staticmethod
    def default_name() -> str:
        return "hooks"
