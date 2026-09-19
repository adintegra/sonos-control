from sonos_control.cli import _print_status, _status_payload, _track_line
from sonos_control.config import Station
from sonos_control.speaker import Playback


def _playback(**overrides) -> Playback:
    data = dict(
        ip="192.168.4.48",
        zone="Kitchen",
        model="SYMFONISK",
        state="PLAYING",
        volume=12,
        muted=False,
        channel="DR P3",
        title="A Song",
        artist="An Artist",
        uri="x-rincon-mp3radio://live-icy.gslb01.dr.dk/A/A05H.mp3",
    )
    data.update(overrides)
    return Playback(**data)


def test_track_line_skips_station_name_as_title():
    assert _track_line(_playback(title="DR P3", artist="")) == ""
    assert _track_line(_playback()) == "An Artist — A Song"


def test_status_payload_includes_matched_station():
    station = Station(key="p3", name="DR P3", url="http://example/p3.mp3")
    payload = _status_payload(_playback(), station)
    assert payload["station"]["key"] == "p3"
    assert payload["ip"] == "192.168.4.48"


def test_print_status(capsys):
    _print_status(
        _playback(),
        Station(key="p3", name="DR P3", url="http://example/p3.mp3"),
    )
    out = capsys.readouterr().out
    assert "Kitchen" in out
    assert "DR P3 (p3)" in out
    assert "An Artist — A Song" in out


def test_namespace_default_ip_help_mentions_correct_address():
    # Guard against the old 192.168.1.48 sneaking back into help text.
    from sonos_control.cli import _build_parser

    help_text = _build_parser().format_help()
    assert "192.168.4.48" in help_text
    assert "192.168.1.48" not in help_text
