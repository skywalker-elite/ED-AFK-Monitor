import time
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import tomllib
try:
	from discord import SyncWebhook
	discord_enabled = True
except ImportError:
	discord_enabled = False
	print('Discord.py unavailable - operating with terminal output only\n')

def fallover(message):
	print(message)
	input('Press ENTER to exit')
	sys.exit()

# Load config file
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
	configfile = Path(__file__).parents[1] / 'afk_monitor.toml'
else:
	configfile = Path(__file__).parent / 'afk_monitor.toml'
if configfile.is_file():
	with open(configfile, "rb") as f:
		config = tomllib.load(f)
else:
	fallover('Config file not found - copy and rename afk_monitor.example.toml to afk_monitor.toml\n')

# Get settings
setting_journal = config['Settings'].get('JournalFolder', '')
setting_utc = config['Settings'].get('UseUTC', False)
setting_fueltank = config['Settings'].get('FuelTank', 64)
discord_webhook = config['Discord'].get('WebhookURL', '')
discord_user = config['Discord'].get('UserID', '')
loglevel = config['LogLevels'] if 'LogLevels' in config else []

# Internals
VERSION = "250205"
GITHUB_LINK = "https://github.com/PsiPab/ED-AFK-Monitor"
DUPE_MAX = 5
FUEL_LOW = 0.2
FUEL_CRIT = 0.1
LOGLEVEL_FALLBACK = 1
SHIPS_EASY = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']
SHIPS_HARD = ['Alliance Crusader', 'Alliance Challenger', 'Alliance Chieftain', 'Anaconda', 'Federal Assault Ship', 'Federal Dropship', 'Federal Gunship', 'Fer-De-Lance', 'Imperial Clipper', 'Krait MK II', 'Python', 'Vulture']
BAIT_MESSAGES = ['$Pirate_ThreatTooHigh', '$Pirate_NotEnoughCargo', '$Pirate_OnNoCargoFound']

class Instance:
	def __init__(self):
		self.scans = []
		self.lastkill = 0
		self.killstime = 0
		self.kills = 0

	def reset(self):
		self.scans = []
		self.lastkill = 0
		self.killstime = 0
		self.kills = 0

class Tracking():
	def __init__(self):
		self.fighterhull = 0
		self.logged = 0
		self.missioncompletes = 0
		self.lastevent = ''
		self.dupemsg = ''
		self.duperepeats = 1
		self.dupewarn = False

session = Instance()
track = Tracking()

if 'https://discord.com' not in discord_webhook:
	discord_enabled = False
	print('Discord webhook not set - operating with terminal output only\n')
elif discord_enabled:
	webhook = SyncWebhook.from_url(config['Discord']['WebhookURL'])

class Col:
	CYAN = '\033[96m'
	YELL = '\033[93m'
	EASY = '\x1b[38;5;157m'
	HARD = '\x1b[38;5;217m'
	WARN = '\x1b[38;5;215m'
	BAD = '\x1b[38;5;15m\x1b[48;5;1m'
	GOOD = '\x1b[38;5;15m\x1b[48;5;2m'
	WHITE = '\033[97m'
	END = '\x1b[0m'

# Set journal folder
if not setting_journal:
	journal_dir = Path.home() / 'Saved Games' / 'Frontier Developments' / 'Elite Dangerous'
else:
	journal_dir = Path(setting_journal)

# Get latest journal file
if not journal_dir.is_dir():
	fallover(f"Directory {journal_dir} not found")

journal_file = ''
for entry in sorted(journal_dir.glob('*.log'), reverse=True):
	if entry.is_file() and entry.name.startswith('Journal.'):
		journal_file = entry.name
		break

if not journal_file:
	fallover(f"Directory {journal_dir} does not contain any journal file")

# Log events
def logevent(msg_term, msg_discord=None, emoji='', timestamp=None, loglevel=1):
	loglevel = int(loglevel)
	if timestamp:
		logtime = timestamp if setting_utc else timestamp.astimezone()
	else:
		logtime = datetime.now(timezone.utc) if setting_utc else datetime.now()
	logtime = datetime.strftime(logtime, '%H:%M:%S')
	if loglevel > 0: print(f'[{logtime}]{emoji} {msg_term}')
	track.logged +=1
	if discord_enabled and loglevel > 1:
		if track.dupemsg == msg_term:
			track.duperepeats += 1
		else:
			track.duperepeats = 1
			track.dupewarn = False
		track.dupemsg = msg_term
		discord_message = msg_discord if msg_discord else f'**{msg_term}**'
		ping = f' <@{discord_user}>' if loglevel > 2 and track.duperepeats == 1 else ''
		if track.duperepeats <= DUPE_MAX:
			webhook.send(f'{emoji} {discord_message} {{{logtime}}}{ping}')
		elif not track.dupewarn:
			webhook.send(f'⏸️ **Suppressing further duplicate messages** {{{logtime}}}')
			track.dupewarn = True

def getloglevel(key=None) -> int:
	if key in loglevel and loglevel.get(key):
		return loglevel.get(key, LOGLEVEL_FALLBACK)
	else:
		print(f'{Col.WHITE}Warning:{Col.END} \'{key}\' not found in config section \'LogLevels\', defaulting to {LOGLEVEL_FALLBACK}')
		return LOGLEVEL_FALLBACK

# Process incoming journal entries
def processevent(line):
	this_json = json.loads(line)
	logtime = datetime.fromisoformat(this_json['timestamp'])

	match this_json['event']:
		case 'ShipTargeted' if 'Ship' in this_json:
			ship = this_json['Ship_Localised'] if 'Ship_Localised' in this_json else this_json['Ship'].title()
			if not ship in session.scans and (ship in SHIPS_EASY or ship in SHIPS_HARD):
				session.scans.append(ship)
				if ship in SHIPS_EASY:
					col = Col.EASY
					log = getloglevel('ScanEasy')
					hard = ''
				else:
					col = Col.HARD
					log = getloglevel('ScanHard')
					hard = ' ☠️'
				logevent(msg_term=f'{col}Scan{Col.END}: {ship}',
						msg_discord=f'**{ship}**{hard}',
						emoji='🔎', timestamp=logtime, loglevel=log)
		case 'Bounty':
			session.scans.clear()
			session.kills +=1
			thiskill = logtime
			killtime_t = ''
			killtime_d = ''
			if session.lastkill:
				seconds = (thiskill-session.lastkill).total_seconds()
				killtime_t = f' [+{time_format(seconds)}]'
				killtime_d = f' **[+{time_format(seconds)}]**'
				session.killstime += seconds
			session.lastkill = logtime

			ship = this_json['Target_Localised'] if 'Target_Localised' in this_json else this_json['Target'].title()
			if ship in SHIPS_EASY:
				col = Col.EASY
				log = getloglevel('KillEasy')
				hard = ''
			else:
				col = Col.HARD
				log = getloglevel('KillHard')
				hard = ' ☠️'
			logevent(msg_term=f'{col}Kill{Col.END}: {ship} ({this_json['VictimFaction']}){killtime_t}',
					msg_discord=f'**{ship}**{hard} ({this_json['VictimFaction']}){killtime_d}',
					emoji='💥', timestamp=logtime, loglevel=log)

			if session.kills % 10 == 0 and this_json['event'] == 'Bounty':
				avgseconds = session.killstime / (session.kills - 1)
				kills_hour = round(3600 / avgseconds, 1)
				logevent(msg_term=f'Session kills: {session.kills} (Avg: {time_format(avgseconds)} | {kills_hour}/h)',
						emoji='📝', timestamp=logtime, loglevel=getloglevel('Reports'))
		case 'MissionRedirected' if 'Mission_Massacre' in this_json['Name']:
			track.missioncompletes += 1
			logevent(msg_term=f'Completed kills for a mission (x{track.missioncompletes})',
					emoji='✅', timestamp=logtime, loglevel=getloglevel('Missions'))
		case 'ReservoirReplenished' if this_json['FuelMain'] < setting_fueltank * FUEL_LOW:
			if this_json['FuelMain'] < setting_fueltank * FUEL_CRIT:
				col = Col.BAD
				fuel_loglevel = getloglevel('FuelCritical')
				level = 'critical'
			else:
				col = Col.WARN
				fuel_loglevel = getloglevel('FuelLow')
				level = 'low'
			fuelremaining = round((this_json['FuelMain'] / setting_fueltank) * 100)
			logevent(msg_term=f'{col}Fuel reserves {level}!{Col.END} (Remaining: {fuelremaining}%)',
					msg_discord=f'**Fuel reserves {level}!** (Remaining: {fuelremaining}%)',
					emoji='⛽', timestamp=logtime, loglevel=fuel_loglevel)
		case 'FighterDestroyed' if track.lastevent != 'StartJump':
			logevent(msg_term=f'{Col.BAD}Fighter destroyed!{Col.END}',
					msg_discord=f'**Fighter destroyed!**',
					emoji='🕹️', timestamp=logtime, loglevel=getloglevel('FighterDown'))
		case 'LaunchFighter' if not this_json['PlayerControlled']:
			logevent(msg_term='Fighter launched',
					emoji='🕹️', timestamp=logtime, loglevel=2)
		case 'ShieldState':
			if this_json['ShieldsUp']:
				shields = 'back up'
				col = Col.GOOD
			else:
				shields = 'down!'
				col = Col.BAD
			logevent(msg_term=f'{col}Ship shields {shields}{Col.END}',
					msg_discord=f'**Ship shields {shields}**',
					emoji='🛡️', timestamp=logtime, loglevel=getloglevel('ShipShields'))
		case 'HullDamage':
			hullhealth = round(this_json['Health'] * 100)
			if this_json['Fighter'] and not this_json['PlayerPilot'] and track.fighterhull != this_json['Health']:
				track.fighterhull = this_json['Health']
				logevent(msg_term=f'{Col.WARN}Fighter hull damaged!{Col.END} (Integrity: {hullhealth}%)',
					msg_discord=f'**Fighter hull damaged!** (Integrity: {hullhealth}%)',
					emoji='🕹️', timestamp=logtime, loglevel=getloglevel('FighterHull'))
			elif this_json['PlayerPilot'] and not this_json['Fighter']:
				logevent(msg_term=f'{Col.BAD}Ship hull damaged!{Col.END} (Integrity: {hullhealth}%)',
					msg_discord=f'**Ship hull damaged!** (Integrity: {hullhealth}%)',
					emoji='🛠️', timestamp=logtime, loglevel=getloglevel('ShipHull'))
		case 'Died':
			logevent(msg_term=f'{Col.BAD}Ship destroyed!{Col.END}',
					msg_discord='**Ship destroyed!**',
					emoji='💀', timestamp=logtime, loglevel=getloglevel('Died'))
		case 'Music' if this_json['MusicTrack'] == 'MainMenu':
			logevent(msg_term='Exited to main menu',
				emoji='🚪', timestamp=logtime, loglevel=2)
		case 'Commander':
			logevent(msg_term=f'Started new session for CMDR {this_json['Name']}',
					emoji='🔄', timestamp=logtime, loglevel=2)
			session.reset()
		case 'SupercruiseDestinationDrop' if '$MULTIPLAYER' in this_json['Type']:
			logevent(msg_term=f'Dropped at {this_json['Type_Localised']}',
					emoji='🚀', timestamp=logtime, loglevel=2)
			session.reset()
		case 'ReceiveText':
			if any(x in this_json['Message'] for x in BAIT_MESSAGES):
				logevent(msg_term=f'{Col.WARN}Pirate didn\'t engage due to insufficient cargo value{Col.END}',
			 			msg_discord='**Pirate didn\'t engage due to insufficient cargo value**',
						emoji='🎣', timestamp=logtime, loglevel=getloglevel('BaitValueLow'))
		case 'EjectCargo' if not this_json["Abandoned"]:
			name = this_json['Type_Localised'] if 'Type_Localised' in this_json else this_json['Type'].title()
			logevent(msg_term=f'{Col.BAD}Cargo ejected!{Col.END} ({name})',
					msg_discord=f'**Cargo ejected!** ({name})',
					emoji='📦', timestamp=logtime, loglevel=getloglevel('CargoLost'))
		case 'Shutdown':
			logevent(msg_term='Quit to desktop',
					emoji='🛑', timestamp=logtime, loglevel=2)
			sys.exit()
	track.lastevent = this_json['event']

def time_format(seconds: int) -> str:
	if seconds is not None:
		seconds = int(seconds)
		h = seconds // 3600 % 24
		m = seconds % 3600 // 60
		s = seconds % 3600 % 60
		if h > 0:
			return '{:d}h{:d}m{:d}s'.format(h, m, s)
		elif m > 0:
			return '{:d}m{:d}s'.format(m, s)
		else:
			return '{:d}s'.format(s)

def header():
	# Print header
	print(f'{Col.CYAN}{'='*37}{Col.END}')
	print(f'{Col.CYAN}ED AFK Monitor v{VERSION} by CMDR PSIPAB{Col.END}')
	print(f'{Col.CYAN}{'='*37}{Col.END}\n')
	print(f'{Col.YELL}Journal folder:{Col.END} {journal_dir}')
	print(f'{Col.YELL}Latest journal:{Col.END} {journal_file}\n')
	print('Starting... (Press Ctrl+C to stop)\n')

if __name__ == '__main__':
	header()
	if discord_enabled:
		webhook.send(f'# 💥 ED AFK Monitor 💥\n-# by CMDR PSIPAB ([v{VERSION}]({GITHUB_LINK}))')
	logevent(msg_term=f'Monitor started ({journal_file})',
			msg_discord=f'**Monitor started** ({journal_file})',
			emoji='📖', loglevel=2)

	# Open journal from end and watch for new lines
	with (journal_dir / journal_file).open() as file:
		file.seek(0, 2)

		try:
			while True:
				line = file.readline()
				if not line:
					time.sleep(1)
					continue

				processevent(line)
		except (KeyboardInterrupt, SystemExit):
			logevent(msg_term=f'Monitor stopped ({journal_file})',
					msg_discord=f'**Monitor stopped** ({journal_file})',
					emoji='📕', loglevel=2)
			if sys.argv[0].count('\\') > 1:
				input('\nPress ENTER to exit')	# This is *still* horrible
				sys.exit()
		except Exception as e:
			print(f"Something went wrong: {e}")
			input("Press ENTER to exit")
