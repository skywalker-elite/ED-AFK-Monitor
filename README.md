# Elite Dangerous AFK Monitor

Real-time monitoring of Elite Dangerous journal files for logging AFK massacre farming events as they happen. Output is to terminal, Discord channel or Discord with a user ping and each level can be configured on a per-event basis.

| Terminal output | Discord output |
| --- | --- |
| ![v250205_terminal](https://github.com/user-attachments/assets/d13f806d-cb97-4638-ab3e-fd30aa9479e1) | ![v250205_discord](https://github.com/user-attachments/assets/21bd198f-7c03-412f-b0ec-5846a7515c40) |

*Screenshots of a simulated log being monitored*

## Contents
- [Elite Dangerous AFK Monitor](#elite-dangerous-afk-monitor)
  - [Contents](#contents)
  - [Events logged](#events-logged)
  - [Getting started](#getting-started)
    - [Standalone (EXE) version](#standalone-exe-version)
    - [Python version](#python-version)
  - [Configuring log levels](#configuring-log-levels)
  - [Common Issues](#common-issues)
    - [I get "Monitor started" but nothing after that](#i-get-monitor-started-but-nothing-after-that)
    - [I'm noticing kills in-game that aren't being logged](#im-noticing-kills-in-game-that-arent-being-logged)
    - [Ships scans not all reported / seem wrong](#ships-scans-not-all-reported--seem-wrong)
    - [Hull was damaged but not reported](#hull-was-damaged-but-not-reported)
    - [I'm getting low fuel level warnings when using a non-AFK ship](#im-getting-low-fuel-level-warnings-when-using-a-non-afk-ship)
    - [I ejected cargo manually and got notified](#i-ejected-cargo-manually-and-got-notified)
    - [There are garbled characters in the terminal output](#there-are-garbled-characters-in-the-terminal-output)

## Events logged

- Ship scans (by player or by NPC pilot in fighter)
- Bounties (i.e. kills) incl. faction and time since previous
- Session kill summary and average times every 10 kills
- Ship shields down/restored
- Ship/fighter hull damage
- Ship/fighter destroyed
- Pirates not engaging due to low cargo value
- Cargo ejected (i.e. stolen)
- Fuel reserves low/critical

...some other minor things

## Getting started

### Standalone (EXE) version

- Download and extract `afk_monitor_standalone.7z` from [releases](https://github.com/PsiPab/ED-AFK-Monitor/releases) to a folder
- Copy `afk_monitor.example.toml` and rename the copy to `afk_monitor.toml`
- (Optional) For Discord support edit `afk_monitor.toml` (instructions in file)
- Start Elite Dangerous then run `afk_monitor.exe`

### Python version

Requirements: [Python 3.x](https://www.python.org/downloads/), [discord.py](https://github.com/Rapptz/discord.py) (optional, required for webhook support)
- Download `Source code (zip)` from [releases](https://github.com/PsiPab/ED-AFK-Monitor/releases) and extract the contents to a folder
- Copy `afk_monitor.example.toml` and rename the copy to `afk_monitor.toml`
- (Optional) For Discord support edit `afk_monitor.toml` (instructions in file)
- Start Elite Dangerous then double-click `afk_monitor.py` *or* open a terminal and run `py afk_monitor.py`

## Configuring log levels

Each type of event can be set to one of four additive output levels - nothing (0), terminal (1), Discord (2) or Discord plus user ping (3). These can be configured by editing the values in `afk_monitor.toml` under the section 'LogLevels'. The event names are intended to be self-descriptive.

By default ED AFK Monitor outputs all events to terminal, all but easy ship type scans to Discord and only sends user pings for important, attention-requiring events. To reset to defaults copy the appropriate values from `afk_monitor.example.toml`.

## Common Issues

### I get "Monitor started" but nothing after that

The program loads your latest journal, so make sure to only start it *after* you have loaded the game or it will monitor the wrong file and produce no output. Note: You don't need to load into gameplay, just up to the main menu is enough to start a new journal.

### I'm noticing kills in-game that aren't being logged

ED does not log all kills/bounties either in-game or to the journal (anywhere from 0-30% are missed). This is a game limitation so there is nothing I can do about it. On the upside, these 'ghost' kills still count towards your missions.

### Ships scans not all reported / seem wrong

Scans are recorded in the journal in the same way when targeted by an NPC pilot *or* the player manually. The only reliable data is that a scan was done of a type of ship, so to keep things from being too spammy we only report each ship type once between kills and then reset after a kill.

In addition, if you manually target a type of ship that pirates also use, e.g. system security, those scans will be logged just like any other. For this reason it is best to only use a target key bind for 'select next hostile target' instead if you have AFK Monitor running with scans enabled.

### Hull was damaged but not reported

ED only records hull damage in 20% increments, so if your ship hull was reduced to 81% for example that wouldn't be reported until it dropped further.

### I'm getting low fuel level warnings when using a non-AFK ship

AFK Monitor currently assumes you are using a ship with a 64t fuel tank such as a T10 Defender or Imperial Cutter. To avoid these erroneous fuel warnings stop the script when not actively engaged in AFK massacre farming.

### I ejected cargo manually and got notified

ED's journal does not differentiate between cargo jettisoned by the player or stolen by hatch breaker limpets. As a workaround if you want to get rid of cargo with the script running and not be notified you can use 'Abandon' instead of 'Jettison'.

### There are garbled characters in the terminal output

Windows 10 command prompt doesn't support nice things like colours or emoji. Install and use [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) instead and things will look *a lot* better.