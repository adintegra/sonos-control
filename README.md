# sonos-control

CLI for a Synfonisk (Sonos) speaker: see what is playing, switch radio streams, and keep shorthand station names in a YAML or JSON file.

Default speaker: `192.168.4.48`

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then either run `sonos` from this directory (it picks up `./stations.yaml`) or copy that file to `~/.config/sonos-control/stations.yaml`.

## Usage

```bash
sonos                 # current station (same as `sonos now`)
sonos play p3         # play a saved shorthand
sonos play https://…  # play a stream URL directly
sonos play            # resume
sonos pause
sonos stop
sonos volume          # show
sonos volume 15       # set 0–100
sonos volume +5
sonos mute
sonos unmute
sonos stations        # list saved shorthands
sonos stations add p5 http://example.com/stream.mp3 -n "DR P5"
sonos stations rm p5
```

`--ip`, `--config FILE`, and `--json` work on every command. `SONOS_IP` and `SONOS_STATIONS` override the defaults.

## Stations file

YAML or JSON. The key is the CLI shorthand:

```yaml
speaker: 192.168.4.48
stations:
  p3:
    name: DR P3
    url: http://live-icy.gslb01.dr.dk/A/A05H.mp3
  jazz: https://example.com/stream.mp3
```

Sonos needs a format it can play (typically MP3 or AAC). HLS/Ogg often will not start.
