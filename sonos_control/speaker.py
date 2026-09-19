"""Thin wrapper around SoCo for the Synfonisk/Sonos LAN API."""

from __future__ import annotations

from dataclasses import dataclass

from soco import SoCo
from soco.exceptions import SoCoException

REQUEST_TIMEOUT = 8.0


class SpeakerError(Exception):
    """Speaker is unreachable or rejected a command."""


@dataclass(frozen=True)
class Playback:
    ip: str
    zone: str
    model: str
    state: str
    volume: int
    muted: bool
    channel: str
    title: str
    artist: str
    uri: str


class Speaker:
    def __init__(self, ip: str, timeout: float = REQUEST_TIMEOUT) -> None:
        self.ip = ip
        self.timeout = timeout
        self.device = SoCo(ip)

    def status(self) -> Playback:
        def read() -> Playback:
            info = self.device.get_speaker_info(timeout=self.timeout)
            transport = self.device.get_current_transport_info()
            media = self.device.get_current_media_info()
            track = self.device.get_current_track_info()
            return Playback(
                ip=self.ip,
                zone=info.get("zone_name") or info.get("player_name") or self.ip,
                model=info.get("model_name") or info.get("model_number") or "",
                state=transport.get("current_transport_state") or "UNKNOWN",
                volume=int(self.device.volume),
                muted=bool(self.device.mute),
                channel=media.get("channel") or "",
                title=track.get("title") or "",
                artist=track.get("artist") or "",
                uri=media.get("uri") or track.get("uri") or "",
            )

        return self._call(read)

    def play_uri(self, uri: str, title: str = "") -> None:
        def play() -> None:
            self.device.play_uri(
                uri,
                title=title,
                force_radio=True,
                timeout=self.timeout,
            )

        self._call(play)

    def play(self) -> None:
        self._call(lambda: self.device.play())

    def pause(self) -> None:
        self._call(lambda: self.device.pause())

    def stop(self) -> None:
        self._call(lambda: self.device.stop())

    def set_volume(self, volume: int) -> int:
        def apply() -> int:
            self.device.volume = max(0, min(100, volume))
            return int(self.device.volume)

        return self._call(apply)

    def adjust_volume(self, delta: int) -> int:
        def apply() -> int:
            self.device.set_relative_volume(delta)
            return int(self.device.volume)

        return self._call(apply)

    def set_mute(self, muted: bool) -> None:
        def apply() -> None:
            self.device.mute = muted

        self._call(apply)

    def _call(self, func):
        try:
            return func()
        except SoCoException as exc:
            raise SpeakerError(f"Speaker at {self.ip} rejected the request: {exc}") from exc
        except OSError as exc:
            raise SpeakerError(
                f"Could not reach speaker at {self.ip}. Is it powered on and on this network?"
            ) from exc
        except Exception as exc:
            message = str(exc).lower()
            if "timed out" in message or "timeout" in message or "connect" in message:
                raise SpeakerError(
                    f"Could not reach speaker at {self.ip}. Is it powered on and on this network?"
                ) from exc
            raise SpeakerError(f"Speaker at {self.ip} failed: {exc}") from exc
