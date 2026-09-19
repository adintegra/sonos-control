from pathlib import Path

import pytest

from sonos_control.config import (
    ConfigError,
    add_station,
    match_station,
    normalize_uri,
    parse_config,
    remove_station,
    resolve_station,
    save_config,
)


SAMPLE = """
speaker: 192.168.4.48
stations:
  p3:
    name: DR P3
    url: http://live-icy.gslb01.dr.dk/A/A05H.mp3
  jazz: https://example.com/jazz.mp3
"""


def test_parse_yaml_and_shorthand_url():
    config = parse_config(SAMPLE)
    assert config.speaker == "192.168.4.48"
    assert config.stations["p3"].name == "DR P3"
    assert config.stations["jazz"].name == "jazz"
    assert config.stations["jazz"].url.endswith("jazz.mp3")


def test_parse_json(tmp_path: Path):
    path = tmp_path / "stations.json"
    path.write_text(
        '{"speaker": "192.168.4.48", "stations": {"p1": {"name": "P1", "url": "http://x/p1.mp3"}}}',
        encoding="utf-8",
    )
    config = parse_config(path.read_text(encoding="utf-8"), path)
    assert config.stations["p1"].url == "http://x/p1.mp3"


def test_resolve_prefix_and_url():
    config = parse_config(SAMPLE)
    assert resolve_station(config, "p").key == "p3"
    assert resolve_station(config, "DR P").name == "DR P3"
    direct = resolve_station(config, "https://stream.example/live")
    assert direct.url == "https://stream.example/live"
    with pytest.raises(ConfigError, match="Unknown station"):
        resolve_station(config, "bbc")


def test_match_station_normalizes_sonos_radio_prefix():
    config = parse_config(SAMPLE)
    matched = match_station(
        config, "x-rincon-mp3radio://live-icy.gslb01.dr.dk/A/A05H.mp3"
    )
    assert matched is not None
    assert matched.key == "p3"
    by_name = match_station(config, "http://other", channel="DR P3")
    assert by_name is not None and by_name.key == "p3"


def test_match_tunein_sonosapi_stream():
    config = parse_config(
        """
        speaker: 192.168.4.48
        stations:
          6music:
            name: BBC Radio 6 Music
            url: x-sonosapi-stream:s44491?sid=254&flags=8224&sn=0
        """
    )
    matched = match_station(
        config, "x-sonosapi-stream:s44491?sid=254&flags=8224&sn=0", channel="BBC Radio 6 Music"
    )
    assert matched is not None
    assert matched.key == "6music"
    assert resolve_station(config, "6").key == "6music"


def test_normalize_uri():
    assert normalize_uri("https://HOST/stream/") == "host/stream"
    assert normalize_uri("x-rincon-mp3radio://HOST/stream") == "host/stream"


def test_add_and_remove_roundtrip(tmp_path: Path):
    config = parse_config(SAMPLE)
    add_station(config, "p1", "http://example.com/p1.mp3", name="DR P1")
    path = save_config(config, tmp_path / "stations.yaml")
    assert path.is_file()
    removed = remove_station(config, "jazz")
    assert removed.key == "jazz"
    assert "jazz" not in config.stations
