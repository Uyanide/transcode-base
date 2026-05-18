"""E-mail notification task via SMTP & Desktop-notification task via notify-send."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from attr import define, frozen

from ..profiles.hooks import MailProfile, NotifyProfile
from ..utils import promote
from .base import ShellRunResult, shell

__all__ = [
    "MailProfile",
    "MailResult",
    "MailRunner",
    "NotifyProfile",
    "NotifyResult",
    "NotifyRunner",
]


@frozen
class MailResult:
    sent: bool


@define
class MailRunner:
    profile: MailProfile
    subject: str
    body: str

    def run(self) -> MailResult:
        if not self.profile.host:
            return MailResult(sent=False)
        msg = EmailMessage()
        msg["Subject"] = self.subject
        msg["From"] = self.profile.user
        msg["To"] = self.profile.to
        msg.set_content(self.body)
        with smtplib.SMTP(self.profile.host, self.profile.port) as smtp:
            if self.profile.use_starttls:
                smtp.starttls()
            if self.profile.user:
                smtp.login(self.profile.user, self.profile.password)
            smtp.send_message(msg)
        return MailResult(sent=True)


@frozen
class NotifyResult(ShellRunResult):
    pass


@define
class NotifyRunner:
    profile: NotifyProfile
    summary: str
    body: str
    error: bool = False

    def build_cmd(self) -> list[str]:
        p = self.profile.error if self.error else self.profile.normal
        return [
            "notify-send",
            f"--app-name={p.app_name}",
            f"--icon={p.icon}",
            f"--urgency={p.urgency}",
            f"--category={p.category}",
            self.summary,
            self.body,
        ]

    def run(self) -> NotifyResult:
        try:
            result = shell(self.build_cmd(), check=False)
        except FileNotFoundError:
            return NotifyResult(returncode=-1, stdout=None, stderr=None, cmd=self.build_cmd())
        except Exception:
            return NotifyResult(returncode=-1, stdout=None, stderr=None, cmd=self.build_cmd())
        return promote(result, NotifyResult)
