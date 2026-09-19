"""Load and save the speaker address plus shorthand station list."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os

import yaml

DEFAULT_SPEAKER_IP = "192.168.4.48"
ENV_SPEAKER_IP = "SONOS_IP"
ENV_STATIONS = "SONOS_STATIONS"
CONFIG_DIRNAME = "sonos-control"
CONFIG_BASENAME = "stations"

_URI_PREFIXES = (
    "x-rincon-mp3radio://",
    "x-rincon-mp3radio:",
    "x-sonosapi-stream:",
    "hls-radio://",
    "hls-radio:",
    "https://",
    "http://",
    "aac://",
    "aac:",
)


class ConfigError(Exception):
    """Invalid or unreadable stations file."""


@dataclass(frozen=True)
class Station:
    key: str
    name: str
    url: str


@dataclass
class Config:
    speaker: str
    stations: dict[str, Station]
    path: Path | None = None

    def station_list(self) -> list[Station]:
        return list(self.stations.values())


def default_user_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / CONFIG_DIRNAME / f"{CONFIG_BASENAME}.yaml"


def find_config_path(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()

    env = os.environ.get(ENV_STATIONS)
    if env:
        return Path(env).expanduser()

    candidates = [
        Path.cwd() / f"{CONFIG_BASENAME}.yaml",
        Path.cwd() / f"{CONFIG_BASENAME}.yml",
        Path.cwd() / f"{CONFIG_BASENAME}.json",
        default_user_config_path(),
        default_user_config_path().with_suffix(".json"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_config(explicit: str | Path | None = None) -> Config:
    path = find_config_path(explicit)
    if path is None:
        return Config(speaker=_default_speaker(), stations={}, path=None)
    if not path.is_file():
        raise ConfigError(f"Stations file not found: {path}")
    return parse_config(path.read_text(encoding="utf-8"), path)


def parse_config(text: str, path: Path | None = None) -> Config:
    data = _decode(text, path)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError("Stations file must be a mapping at the top level.")

    speaker = str(data.get("speaker") or _default_speaker()).strip()
    if not speaker:
        speaker = _default_speaker()

    raw_stations = data.get("stations") or {}
    if not isinstance(raw_stations, dict):
        raise ConfigError("'stations' must be a mapping of shorthand → station.")

    stations: dict[str, Station] = {}
    for key, value in raw_stations.items():
        alias = str(key).strip()
        if not alias:
            raise ConfigError("Station shorthand cannot be empty.")
        stations[alias.lower()] = _parse_station(alias, value)
    return Config(speaker=speaker, stations=stations, path=path)


def save_config(config: Config, path: Path | None = None) -> Path:
    dest = path or config.path or default_user_config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "speaker": config.speaker,
        "stations": {
            station.key: {"name": station.name, "url": station.url}
            for station in config.station_list()
        },
    }
    if dest.suffix.lower() == ".json":
        dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    else:
        dest.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    config.path = dest
    return dest


def add_station(config: Config, key: str, url: str, name: str | None = None) -> Station:
    alias = key.strip()
    if not alias:
        raise ConfigError("Station shorthand cannot be empty.")
    if not looks_like_url(url):
        raise ConfigError(f"Not a stream URL: {url}")
    station = Station(key=alias, name=(name or alias).strip(), url=url.strip())
    config.stations[alias.lower()] = station
    return station


def remove_station(config: Config, key: str) -> Station:
    station = resolve_station(config, key, urls_allowed=False)
    del config.stations[station.key.lower()]
    return station


def resolve_station(
    config: Config, query: str, urls_allowed: bool = True
) -> Station:
    text = query.strip()
    if urls_allowed and looks_like_url(text):
        return Station(key="", name=text, url=text)

    lowered = text.lower()
    exact = config.stations.get(lowered)
    if exact:
        return exact

    matches = [
        station
        for station in config.station_list()
        if station.key.lower().startswith(lowered)
        or station.name.lower().startswith(lowered)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        aliases = ", ".join(station.key for station in matches)
        raise ConfigError(f"Ambiguous station '{query}'. Matches: {aliases}")

    known = ", ".join(station.key for station in config.station_list()) or "(none)"
    raise ConfigError(f"Unknown station '{query}'. Saved stations: {known}")


def match_station(config: Config, uri: str, channel: str = "") -> Station | None:
    normalized = normalize_uri(uri)
    if normalized:
        for station in config.station_list():
            if normalize_uri(station.url) == normalized:
                return station
    label = (channel or "").strip().lower()
    if label:
        for station in config.station_list():
            if station.name.lower() == label or station.key.lower() == label:
                return station
    return None


def looks_like_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith(
        (
            "http://",
            "https://",
            "aac://",
            "x-rincon-mp3radio:",
            "x-sonosapi-stream:",
            "hls-radio:",
        )
    )


def normalize_uri(uri: str) -> str:
    text = (uri or "").strip()
    lowered = text.lower()
    for prefix in _URI_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.rstrip("/").lower()


def _default_speaker() -> str:
    return os.environ.get(ENV_SPEAKER_IP, DEFAULT_SPEAKER_IP).strip() or DEFAULT_SPEAKER_IP


def _decode(text: str, path: Path | None) -> object:
    suffix = path.suffix.lower() if path else ""
    if suffix == ".json":
        try:
            return json.loads(text) if text.strip() else {}
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    return loaded


def _parse_station(key: str, value: object) -> Station:
    if isinstance(value, str):
        url = value.strip()
        if not looks_like_url(url):
            raise ConfigError(f"Station '{key}' needs a stream URL, got {value!r}")
        return Station(key=key, name=key, url=url)
    if isinstance(value, dict):
        url = str(value.get("url") or "").strip()
        name = str(value.get("name") or key).strip()
        if not looks_like_url(url):
            raise ConfigError(f"Station '{key}' is missing a valid 'url'.")
        return Station(key=key, name=name, url=url)
    raise ConfigError(f"Station '{key}' must be a URL string or a {{name, url}} mapping.")
