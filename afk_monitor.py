import os
import time
import json
from pathlib import Path
import argparse
import sys
from datetime import datetime, timezone
try:
	from discord import SyncWebhook
	discord_avail = True
except ImportError:
	discord_avail = False
	print('Discord.py unavailable - operating with terminal output only\n')

# Config
use_utc = False
fuel_tank = 64	# Standard size for T10 & Cutter
discord_webhook = ''	# Discord webhook URL
discord_userid = ''		# Discord user ID for pings

version = "250129"
ships_easy = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']
ships_hard = ['Alliance Crusader', 'Alliance Challenger', 'Alliance Chieftain', 'Anaconda', 'Federal Assault Ship', 'Federal Dropship', 'Federal Gunship', 'Fer-De-Lance', 'Imperial Clipper', 'Krait MK II', 'Python', 'Vulture']
bait_messages = ['$Pirate_ThreatTooHigh', '$Pirate_NotEnoughCargo', '$Pirate_OnNoCargoFound']

LOG_NONE = 0
LOG_TERM = 1
LOG_BOTH = 2
LOG_PING = 3

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
if discord_avail: webhook = SyncWebhook.from_url(discord_webhook)

class Col:
	CYAN = '\033[96m'
	YELL = '\033[93m'
	EASY = '\x1b[38;5;157m'
	HARD = '\x1b[38;5;217m'
	WARN = '\x1b[38;5;215m'
	BAD = '\x1b[38;5;15m\x1b[48;5;1m'
	GOOD = '\x1b[38;5;15m\x1b[48;5;2m'
	END = '\x1b[0m'

# Arguments
parser = argparse.ArgumentParser(
    prog='AFK Monitor',
    description='Live event monitoring for Elite Dangerous AFK sessions')
parser.add_argument('-j', '--journal_folder', help='override default journal location')
args = parser.parse_args()

# Set journal folder
if not args.journal_folder:
	home_dir = str(Path.home())
	journal_dir = home_dir+'\\Saved Games\\Frontier Developments\\Elite Dangerous'
else:
	journal_dir = args.journal_folder

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
	if timestamp:
		logtime = logtime if use_utc else timestamp.astimezone()
	else:
		logtime = datetime.now(timezone.utc) if use_utc else datetime.now()
	logtime = datetime.strftime(logtime, '%H:%M:%S')
	if loglevel > 0: print(f'[{logtime}]{emoji} {msg_term}')
	track.logged +=1
	if discord_avail and loglevel > 1:
		discord_message = msg_discord if msg_discord else f'**{msg_term}**'
		ping = f' <@{discord_userid}>' if loglevel > 2 else ''
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
				hard = '(!)' if ship in ships_hard else ''
				logevent(msg_term=f'{col}Scan{Col.END}: {ship}{hard}',
						msg_discord=f'**{ship}**{hard}',
						emoji='🔎', timestamp=logtime, loglevel=LOG_TERM)
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
			hard = '(!)' if ship in ships_hard else ''
			logevent(msg_term=f'{col}Kill{Col.END}: {ship}{hard} ({this_json['VictimFaction']}){killtime_t}',
					msg_discord=f'**{ship}{hard}** ({this_json['VictimFaction']}){killtime_d}',
					emoji='💥', timestamp=logtime, loglevel=LOG_BOTH)
			
			if session.kills % 10 == 0 and this_json['event'] == 'Bounty':
				avgtime = time_format(session.killstime / (session.kills - 1))
				logevent(msg_term=f'Session kills: {session.kills} (Avg time: {avgtime})',
						emoji='📝', timestamp=logtime, loglevel=LOG_BOTH)
		case 'MissionRedirected' if 'Mission_Massacre' in this_json['Name']:
			track.missioncompletes += 1
			logevent(msg_term=f'Completed kills for a mission ({track.missioncompletes})',
					emoji='✅', timestamp=logtime, loglevel=LOG_BOTH)
		case 'ReservoirReplenished' if this_json['FuelMain'] < fuel_tank * 0.2:
			col = Col.BAD if this_json['FuelMain'] < fuel_tank * 0.1 else Col.WARN
			fuelremaining = round((this_json['FuelMain'] / fuel_tank) * 100)
			logevent(msg_term=f'{col}Fuel reserves low!{Col.END} (Remaining: {fuelremaining}%)',
					msg_discord=f'**Fuel reserves low!** (Remaining: {fuelremaining}%)',
					emoji='⛽', timestamp=logtime, loglevel=LOG_BOTH)
		case 'FighterDestroyed':
			logevent(msg_term=f'{Col.BAD}Fighter destroyed!{Col.END}',
					msg_discord=f'**Fighter destroyed!**',
					emoji='🕹️', timestamp=logtime, loglevel=LOG_PING)
		case 'LaunchFighter' if not this_json['PlayerControlled']:
			logevent(msg_term='Fighter launched',
					emoji='🕹️', timestamp=logtime, loglevel=LOG_BOTH)
		case 'ShieldState':
			if this_json['ShieldsUp']: 
				shields = 'back up'
				col = Col.GOOD
			else:
				shields = 'down!'
				col = Col.BAD
			logevent(msg_term=f'{col}Ship shields {shields}{Col.END}',
					msg_discord=f'**Ship shields {shields}**',
					emoji='🛡️', timestamp=logtime, loglevel=LOG_PING)
		case 'HullDamage' if this_json['Fighter'] and track.fighterhull != this_json['Health']:
			track.fighterhull = this_json['Health']
			hullhealth = round(this_json['Health'] * 100)
			logevent(msg_term=f'{Col.WARN}Fighter hull damaged!{Col.END} (Health: {hullhealth}%)',
					msg_discord=f'**Fighter hull damaged!** (Health: {hullhealth}%)',
					emoji='🕹️', timestamp=logtime, loglevel=LOG_BOTH)
		case 'HullDamage' if this_json['PlayerPilot']:
			hullhealth = round(this_json['Health'] * 100)
			logevent(msg_term=f'{Col.BAD}Ship hull damaged!{Col.END} (Health: {hullhealth}%)',
					msg_discord=f'**Ship hull damaged!** (Health: {hullhealth}%)',
					emoji='🛠️', timestamp=logtime, loglevel=LOG_PING)
		case 'Died':
			logevent(msg_term=f'{Col.BAD}Ship destroyed!{Col.END}',
					msg_discord='**Ship destroyed!**',
					emoji='💀', timestamp=logtime, loglevel=LOG_PING)
		case 'Music' if this_json['MusicTrack'] == 'MainMenu':
			logevent(msg_term='Exited to main menu',
				emoji='🚪', timestamp=logtime, loglevel=LOG_BOTH)
		case 'Commander':
			logevent(msg_term=f'Started new session for CMDR {this_json['Name']}',
					emoji='🔄', timestamp=logtime, loglevel=LOG_BOTH)
			session.reset()
		case 'SupercruiseDestinationDrop' if '$MULTIPLAYER' in this_json['Type']:
			logevent(msg_term=f'Dropped at {this_json['Type_Localised']}',
					emoji='🚀', timestamp=logtime, loglevel=LOG_BOTH)
			session.reset()
		case 'ReceiveText':
			if any(x in this_json['Message'] for x in bait_messages):
				logevent(msg_term=f'{Col.WARN}Pirate didn\'t engage due to insufficient cargo value{Col.END}',
			 			msg_discord='**Pirate didn\'t engage due to insufficient cargo value**',
						emoji='🎣', timestamp=logtime, loglevel=LOG_BOTH)
		case 'EjectCargo' if not this_json["Abandoned"]:
			name = this_json['Type_Localised'] if 'Type_Localised' else this_json['Type'].title()
			logevent(msg_term=f'{Col.BAD}Cargo ejected!{Col.END} ({name})',
					msg_discord=f'**Cargo ejected!** ({name})',
					emoji='📦', timestamp=logtime, loglevel=LOG_PING)
		case 'Shutdown':
			logevent(msg_term='Quit to desktop',
					emoji='🛑', timestamp=logtime, loglevel=LOG_BOTH)
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
			emoji='📖', loglevel=LOG_BOTH)

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
					emoji='📕', loglevel=LOG_BOTH)
			if sys.argv[0].count('\\') > 1: input('\nPress ENTER to exit')	# This is *still* horrible
		except:
			input("Something went wrong, hit ENTER to exit")