# sonos-control

CLI for a Synfonisk (Sonos) speaker: see what is playing, switch radio streams, and keep shorthand station names in a YAML or JSON file.

## Install

Set the IP address of your speaker in an environment variable `ENV_SPEAKER_IP` or change the default address in `sonos_control/config.py` by updating the variable `DEFAULT_SPEAKER_IP`.

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

## Desktop shortcut (macOS)

`scripts/play-radio-paradise.command` starts Radio Paradise on the Synfonisk. Double-click it in Finder (or a copy on the Desktop).

```bash
chmod +x scripts/play-radio-paradise.command
cp scripts/play-radio-paradise.command ~/Desktop/Radio\ Paradise.command
```

The first time, macOS may ask you to allow Terminal to run the file. After that it plays the `rp` station and shows a notification. The script uses the project `.venv` and `stations.yaml`, so keep those in place (or edit the paths inside the `.command` if you move the repo).

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
