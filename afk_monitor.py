import os
import time
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import configparser
try:
	from discord import SyncWebhook
	discord_avail = True
except ImportError:
	discord_avail = False
	print('Discord.py unavailable - operating with terminal output only\n')
	input('Press ENTER to exit')

# Load config file
config = configparser.ConfigParser()
configfile = Path(os.path.dirname(__file__)+'\\afk_monitor.ini')
if configfile.is_file():
	config.read(configfile)
else:
	print('Config file not found - copy/rename afk_monitor.example.ini to afk_monitor.ini\n')
	input('Press ENTER to exit')
	sys.exit()

# Get settings
journal_folder = config['Settings']['JournalFolder']
use_utc = config['Settings'].getboolean('UseUTC', False)
fuel_tank = config['Settings'].getint('FuelTank', 64)
loglevel = config['LogLevels']
discord_webhook = config['Discord']['WebhookURL']
discord_user = config['Discord']['UserID']

# Internals
version = "250130"
ships_easy = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']
ships_hard = ['Alliance Crusader', 'Alliance Challenger', 'Alliance Chieftain', 'Anaconda', 'Federal Assault Ship', 'Federal Dropship', 'Federal Gunship', 'Fer-De-Lance', 'Imperial Clipper', 'Krait MK II', 'Python', 'Vulture']
bait_messages = ['$Pirate_ThreatTooHigh', '$Pirate_NotEnoughCargo', '$Pirate_OnNoCargoFound']

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

session = Instance()
track = Tracking()

if discord_webhook[:19] != 'https://discord.com': discord_avail = False
if discord_avail:
	webhook = SyncWebhook.from_url(config['Discord']['WebhookURL'])

class Col:
	CYAN = '\033[96m'
	YELL = '\033[93m'
	EASY = '\x1b[38;5;157m'
	HARD = '\x1b[38;5;217m'
	WARN = '\x1b[38;5;215m'
	BAD = '\x1b[38;5;15m\x1b[48;5;1m'
	GOOD = '\x1b[38;5;15m\x1b[48;5;2m'
	END = '\x1b[0m'

# Set journal folder
if not journal_folder:
	home_dir = str(Path.home())
	journal_dir = home_dir+'\\Saved Games\\Frontier Developments\\Elite Dangerous'
else:
	journal_dir = journal_folder

# Get latest journal file
files = []
fileslist = os.scandir(journal_dir)
for entry in fileslist:
	if entry.is_file():
		if entry.name[:7] == 'Journal':
			files.append(entry.name)
fileslist.close()
journal_file = files[len(files)-1]

# Log events
def logevent(msg_term, msg_discord=None, emoji='', timestamp=None, loglevel=1):
	loglevel = int(loglevel)
	if timestamp:
		logtime = timestamp if use_utc else timestamp.astimezone()
	else:
		logtime = datetime.now(timezone.utc) if use_utc else datetime.now()
	logtime = datetime.strftime(logtime, '%H:%M:%S')
	if loglevel > 0: print(f'[{logtime}]{emoji} {msg_term}')
	track.logged +=1
	if discord_avail and loglevel > 1:
		discord_message = msg_discord if msg_discord else f'**{msg_term}**'
		ping = f' <@{discord_user}>' if loglevel > 2 else ''
		webhook.send(f'{emoji} {discord_message} {{{logtime}}}{ping}')

# Process incoming journal entries
def processevent(line):
	this_json = json.loads(line)
	logtime = datetime.fromisoformat(this_json['timestamp'])
	
	match this_json['event']:
		case 'ShipTargeted' if 'Ship' in this_json:
			ship = this_json['Ship_Localised'] if 'Ship_Localised' in this_json else this_json['Ship'].title()
			if not ship in session.scans and (ship in ships_easy or ship in ships_hard):
				session.scans.append(ship)
				col = Col.EASY if ship in ships_easy else Col.HARD
				hard = ' ☠️' if ship in ships_hard else ''
				logevent(msg_term=f'{col}Scan{Col.END}: {ship}',
						msg_discord=f'**{ship}**{hard}',
						emoji='🔎', timestamp=logtime, loglevel=loglevel['Scans'])
		case 'Bounty':
			session.scans.clear()
			session.kills +=1
			thiskill = logtime
			killtime_t = ''
			killtime_d = ''
			if session.lastkill:
				seconds = (thiskill-session.lastkill).total_seconds()
				killtime_t = f' [+{time_format(seconds)}]'
				killtime_d = f' **{killtime_t}**'
				session.killstime += seconds
			session.lastkill = logtime

			ship = this_json['Target_Localised'] if 'Target_Localised' in this_json else this_json['Target'].title()
			col = Col.HARD if ship in ships_hard else Col.EASY
			hard = ' ☠️' if ship in ships_hard else ''
			logevent(msg_term=f'{col}Kill{Col.END}: {ship} ({this_json['VictimFaction']}){killtime_t}',
					msg_discord=f'**{ship}**{hard} ({this_json['VictimFaction']}){killtime_d}',
					emoji='💥', timestamp=logtime, loglevel=loglevel['Kills'])
			
			if session.kills % 10 == 0 and this_json['event'] == 'Bounty':
				avgtime = time_format(session.killstime / (session.kills - 1))
				logevent(msg_term=f'Session kills: {session.kills} (Avg time: {avgtime})',
						emoji='📝', timestamp=logtime, loglevel=loglevel['Reports'])
		case 'MissionRedirected' if 'Mission_Massacre' in this_json['Name']:
			track.missioncompletes += 1
			logevent(msg_term=f'Completed kills for a mission ({track.missioncompletes})',
					emoji='✅', timestamp=logtime, loglevel=loglevel['Missions'])
		case 'ReservoirReplenished' if this_json['FuelMain'] < fuel_tank * 0.2:
			if this_json['FuelMain'] < fuel_tank * 0.1:
				col = Col.BAD
				fuel_loglevel = loglevel['FuelCritical']
				level = 'critical'
			else:
				col = Col.WARN
				fuel_loglevel = loglevel['FuelLow']
				level = 'low'
			fuelremaining = round((this_json['FuelMain'] / fuel_tank) * 100)
			logevent(msg_term=f'{col}Fuel reserves {level}!{Col.END} (Remaining: {fuelremaining}%)',
					msg_discord=f'**Fuel reserves {level}!** (Remaining: {fuelremaining}%)',
					emoji='⛽', timestamp=logtime, loglevel=fuel_loglevel)
		case 'FighterDestroyed':
			logevent(msg_term=f'{Col.BAD}Fighter destroyed!{Col.END}',
					msg_discord=f'**Fighter destroyed!**',
					emoji='🕹️', timestamp=logtime, loglevel=loglevel['FighterDown'])
		case 'LaunchFighter' if not this_json['PlayerControlled']:
			logevent(msg_term='Fighter launched',
					emoji='🕹️', timestamp=logtime, loglevel=loglevel['Default'])
		case 'ShieldState':
			if this_json['ShieldsUp']: 
				shields = 'back up'
				col = Col.GOOD
			else:
				shields = 'down!'
				col = Col.BAD
			logevent(msg_term=f'{col}Ship shields {shields}{Col.END}',
					msg_discord=f'**Ship shields {shields}**',
					emoji='🛡️', timestamp=logtime, loglevel=loglevel['ShipShields'])
		case 'HullDamage':
			hullhealth = round(this_json['Health'] * 100)
			if this_json['Fighter'] and not this_json['PlayerPilot'] and track.fighterhull != this_json['Health']:
				track.fighterhull = this_json['Health']
				logevent(msg_term=f'{Col.WARN}Fighter hull damaged!{Col.END} (Health: {hullhealth}%)',
					msg_discord=f'**Fighter hull damaged!** (Health: {hullhealth}%)',
					emoji='🕹️', timestamp=logtime, loglevel=loglevel['FighterHull'])
			elif this_json['PlayerPilot'] and not this_json['Fighter']:
				logevent(msg_term=f'{Col.BAD}Ship hull damaged!{Col.END} (Health: {hullhealth}%)',
					msg_discord=f'**Ship hull damaged!** (Health: {hullhealth}%)',
					emoji='🛠️', timestamp=logtime, loglevel=loglevel['ShipHull'])
		case 'Died':
			logevent(msg_term=f'{Col.BAD}Ship destroyed!{Col.END}',
					msg_discord='**Ship destroyed!**',
					emoji='💀', timestamp=logtime, loglevel=loglevel['Died'])
		case 'Music' if this_json['MusicTrack'] == 'MainMenu':
			logevent(msg_term='Exited to main menu',
				emoji='🚪', timestamp=logtime, loglevel=loglevel['Default'])
		case 'Commander':
			logevent(msg_term=f'Started new session for CMDR {this_json['Name']}',
					emoji='🔄', timestamp=logtime, loglevel=loglevel['Default'])
			session.reset()
		case 'SupercruiseDestinationDrop' if '$MULTIPLAYER' in this_json['Type']:
			logevent(msg_term=f'Dropped at {this_json['Type_Localised']}',
					emoji='🚀', timestamp=logtime, loglevel=loglevel['Default'])
			session.reset()
		case 'ReceiveText':
			if any(x in this_json['Message'] for x in bait_messages):
				logevent(msg_term=f'{Col.WARN}Pirate didn\'t engage due to insufficient cargo value{Col.END}',
			 			msg_discord='**Pirate didn\'t engage due to insufficient cargo value**',
						emoji='🎣', timestamp=logtime, loglevel=loglevel['BaitValueLow'])
		case 'EjectCargo' if not this_json["Abandoned"]:
			name = this_json['Type_Localised'] if 'Type_Localised' else this_json['Type'].title()
			logevent(msg_term=f'{Col.BAD}Cargo ejected!{Col.END} ({name})',
					msg_discord=f'**Cargo ejected!** ({name})',
					emoji='📦', timestamp=logtime, loglevel=loglevel['CargoLost'])
		case 'Shutdown':
			logevent(msg_term='Quit to desktop',
					emoji='🛑', timestamp=logtime, loglevel=loglevel['Default'])
			sys.exit()

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
		elif s > 0:
			return '{:d}s'.format(s)
		elif seconds == 0:
			return '0s'

if __name__ == '__main__':
	# Print header
	print(f'{Col.CYAN}{'='*37}{Col.END}')
	print(f'{Col.CYAN}ED AFK Monitor v{version} by CMDR PSIPAB{Col.END}')
	print(f'{Col.CYAN}{'='*37}{Col.END}\n')
	print(f'{Col.YELL}Journal folder:{Col.END} {journal_dir}')
	print(f'{Col.YELL}Latest journal:{Col.END} {journal_file}\n')
	print(f'Starting... (Press Ctrl+C to stop)\n')
	logevent(msg_term=f'ED AFK Monitor v{version} started',
			emoji='📖', loglevel=2)

	# Open journal from end and watch for new lines
	with open(journal_dir+'\\'+journal_file, 'r') as file:
		file.seek(0, 2)

		try:
			while True:
				line = file.readline()
				if not line:
					time.sleep(1)
					continue
				
				processevent(line)
		except (KeyboardInterrupt, SystemExit):
			logevent(msg_term=f'ED AFK Monitor stopped ({journal_file})',
					msg_discord=f'**ED AFK Monitor stopped** ({journal_file})',
					emoji='📕', loglevel=2)
			if sys.argv[0].count('\\') > 1: input('\nPress ENTER to exit')	# This is *still* horrible
		except:
			input("Something went wrong, hit ENTER to exit")