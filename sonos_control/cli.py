"""Command-line interface for the Synfonisk/Sonos controller."""

from __future__ import annotations

import argparse
import json
import sys
import time

from sonos_control import __version__
from sonos_control.config import (
    Config,
    ConfigError,
    add_station,
    default_user_config_path,
    load_config,
    match_station,
    remove_station,
    resolve_station,
    save_config,
)
from sonos_control.speaker import Playback, Speaker, SpeakerError

_STATE_LABELS = {
    "PLAYING": "playing",
    "PAUSED_PLAYBACK": "paused",
    "STOPPED": "stopped",
    "TRANSITIONING": "switching",
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, SpeakerError) as exc:
        print(exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sonos",
        description="Check or change the radio stream on a Synfonisk/Sonos speaker.",
    )
    parser.add_argument("--ip", help="Speaker IP (default: 192.168.4.48 or stations file).")
    parser.add_argument(
        "--config",
        metavar="FILE",
        help="Stations file (YAML or JSON). Default: ./stations.yaml or ~/.config/sonos-control/stations.yaml",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON for status commands.",
    )
    parser.add_argument("--version", action="version", version=f"sonos-control {__version__}")
    parser.set_defaults(func=cmd_now)

    sub = parser.add_subparsers(dest="command")

    now = sub.add_parser("now", aliases=["status"], help="Show the station currently tuned in.")
    now.set_defaults(func=cmd_now)

    play = sub.add_parser("play", help="Play a saved station shorthand, a stream URL, or resume.")
    play.add_argument(
        "station",
        nargs="?",
        help="Station shorthand (e.g. p3) or a full stream URL. Omit to resume.",
    )
    play.set_defaults(func=cmd_play)

    pause = sub.add_parser("pause", help="Pause playback.")
    pause.set_defaults(func=cmd_pause)

    stop = sub.add_parser("stop", help="Stop playback.")
    stop.set_defaults(func=cmd_stop)

    volume = sub.add_parser("volume", help="Show or set volume (0-100, or +N/-N).")
    volume.add_argument("level", nargs="?", help="Absolute level, or a relative change such as +5.")
    volume.set_defaults(func=cmd_volume)

    mute = sub.add_parser("mute", help="Mute the speaker.")
    mute.set_defaults(func=cmd_mute)

    unmute = sub.add_parser("unmute", help="Unmute the speaker.")
    unmute.set_defaults(func=cmd_unmute)

    stations = sub.add_parser("stations", help="List, add, or remove saved stations.")
    stations.set_defaults(func=cmd_stations_list)
    station_sub = stations.add_subparsers(dest="stations_command")

    station_sub.add_parser("list", help="List saved stations.").set_defaults(func=cmd_stations_list)

    add = station_sub.add_parser("add", help="Save a shorthand → stream URL.")
    add.add_argument("key", help="Shorthand used on the command line, e.g. p3")
    add.add_argument("url", help="Streaming URL the speaker should play")
    add.add_argument("--name", "-n", help="Display name (defaults to the shorthand)")
    add.set_defaults(func=cmd_stations_add)

    remove = station_sub.add_parser("rm", aliases=["remove"], help="Remove a saved station.")
    remove.add_argument("key", help="Shorthand to delete")
    remove.set_defaults(func=cmd_stations_remove)

    return parser


def cmd_now(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    playback = _speaker(args, config).status()
    station = match_station(config, playback.uri, playback.channel)
    if args.json:
        _print_json(_status_payload(playback, station))
        return 0
    _print_status(playback, station)
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    speaker = _speaker(args, config)
    if not args.station:
        speaker.play()
        if not args.json:
            print("Resumed playback.")
        return cmd_now(args) if args.json else 0

    station = resolve_station(config, args.station)
    speaker.play_uri(station.url, title=station.name)
    time.sleep(2)
    playback = speaker.status()
    if args.json:
        _print_json(_status_payload(playback, match_station(config, playback.uri, playback.channel)))
        return 0 if playback.state != "STOPPED" else 2
    label = f"{station.name} ({station.key})" if station.key else station.name
    if playback.state == "STOPPED":
        print(
            f"Speaker queued {label} but did not start. "
            "This stream URL is likely unsupported (unusual port, TLS, or codec).",
            file=sys.stderr,
        )
        return 2
    print(f"Playing {label}")
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    _speaker(args, load_config(args.config)).pause()
    print("Paused.")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    _speaker(args, load_config(args.config)).stop()
    print("Stopped.")
    return 0


def cmd_volume(args: argparse.Namespace) -> int:
    speaker = _speaker(args, load_config(args.config))
    if args.level is None:
        playback = speaker.status()
        if args.json:
            _print_json({"volume": playback.volume, "muted": playback.muted})
        else:
            muted = " (muted)" if playback.muted else ""
            print(f"{playback.volume}{muted}")
        return 0

    level = args.level.strip()
    if level.startswith(("+", "-")) and level[1:].isdigit():
        volume = speaker.adjust_volume(int(level))
    elif level.isdigit():
        volume = speaker.set_volume(int(level))
    else:
        raise ConfigError("Volume must be 0-100, or a relative change such as +5 or -3.")

    if args.json:
        _print_json({"volume": volume})
    else:
        print(volume)
    return 0


def cmd_mute(args: argparse.Namespace) -> int:
    _speaker(args, load_config(args.config)).set_mute(True)
    print("Muted.")
    return 0


def cmd_unmute(args: argparse.Namespace) -> int:
    _speaker(args, load_config(args.config)).set_mute(False)
    print("Unmuted.")
    return 0


def cmd_stations_list(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    stations = config.station_list()
    if args.json:
        _print_json(
            {
                "speaker": config.speaker,
                "file": str(config.path) if config.path else None,
                "stations": [
                    {"key": station.key, "name": station.name, "url": station.url}
                    for station in stations
                ],
            }
        )
        return 0
    if not stations:
        hint = config.path or default_user_config_path()
        print("No stations saved yet.")
        print(f"Add one with:  sonos stations add p3 http://example.com/stream.mp3 -n 'DR P3'")
        print(f"File: {hint}")
        return 0
    width = max(len(station.key) for station in stations)
    print(f"Speaker {config.speaker}" + (f"  ({config.path})" if config.path else ""))
    for station in stations:
        print(f"  {station.key:<{width}}  {station.name}  {station.url}")
    return 0


def cmd_stations_add(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    dest = _writable_config_path(args, config)
    station = add_station(config, args.key, args.url, args.name)
    save_config(config, dest)
    print(f"Saved {station.key} → {station.name} ({station.url})")
    print(f"Wrote {dest}")
    return 0


def cmd_stations_remove(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    dest = _writable_config_path(args, config)
    station = remove_station(config, args.key)
    save_config(config, dest)
    print(f"Removed {station.key}")
    print(f"Wrote {dest}")
    return 0


def _speaker(args: argparse.Namespace, config: Config) -> Speaker:
    return Speaker(args.ip or config.speaker)


def _writable_config_path(args: argparse.Namespace, config: Config):
    if args.config:
        return args.config
    if config.path:
        return config.path
    return default_user_config_path()


def _print_status(playback: Playback, station) -> None:
    state = _STATE_LABELS.get(playback.state, playback.state.lower())
    header = playback.zone or playback.ip
    extras = [part for part in (playback.model, state) if part]
    print(f"{header} · {' · '.join(extras)}")

    if station:
        print(f"  Station  {station.name} ({station.key})")
    elif playback.channel:
        print(f"  Station  {playback.channel}")
    elif playback.uri:
        print("  Station  (unknown)")
    else:
        print("  Station  (nothing queued)")

    track = _track_line(playback)
    if track:
        print(f"  Track    {track}")
    if playback.uri:
        print(f"  Stream   {playback.uri}")
    muted = " muted" if playback.muted else ""
    print(f"  Volume   {playback.volume}{muted}")


def _track_line(playback: Playback) -> str:
    title = playback.title.strip()
    artist = playback.artist.strip()
    channel = playback.channel.strip()
    if title and title.lower() == channel.lower():
        title = ""
    if artist and title:
        return f"{artist} — {title}"
    return title or artist


def _status_payload(playback: Playback, station) -> dict:
    return {
        "ip": playback.ip,
        "zone": playback.zone,
        "model": playback.model,
        "state": playback.state,
        "volume": playback.volume,
        "muted": playback.muted,
        "channel": playback.channel,
        "title": playback.title,
        "artist": playback.artist,
        "uri": playback.uri,
        "station": (
            {"key": station.key, "name": station.name, "url": station.url}
            if station
            else None
        ),
    }


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2))
