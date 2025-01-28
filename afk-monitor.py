import os
import time
import json
from pathlib import Path
import argparse
import sys
from datetime import datetime

# Config
log_scans = True
log_bounties = True
fuel_tank = 64	# Standard size for T10 & Cutter

version = "250127"
ships_easy = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']
ships_hard = ['Alliance Crusader', 'Alliance Challenger', 'Alliance Chieftain', 'Anaconda', 'Federal Assault Ship', 'Federal Dropship', 'Federal Gunship', 'Fer-De-Lance', 'Imperial Clipper', 'Krait MK II', 'Python', 'Vulture']
bait_messages = ['$Pirate_ThreatTooHigh', '$Pirate_NotEnoughCargo', '$Pirate_OnNoCargoFound']

class Col:
	EASY = '\x1b[38;5;157m'
	HARD = '\x1b[38;5;217m'
	WARN = '\x1b[38;5;215m'
	BAD = '\x1b[38;5;15m\x1b[48;5;1m'
	GOOD = '\x1b[38;5;15m\x1b[48;5;2m'
	END = '\x1b[0m'

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

session = Instance()
track = Tracking()

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
def logevent(message, emoji='', time=datetime.now()):
	timestamp = datetime.strftime(time, '%H:%M:%S')
	print(f'[{timestamp}]{emoji} {message}')
	track.logged +=1

# Process incoming journal entries
def processevent(line):
	this_json = json.loads(line)
	logtime = datetime.fromisoformat(this_json['timestamp'])
	
	match this_json['event']:
		case 'ShipTargeted' if log_scans and 'Ship' in this_json:
			ship = this_json['Ship_Localised'] if 'Ship_Localised' in this_json else this_json['Ship'].title()
			if not ship in session.scans and (ship in ships_easy or ship in ships_hard):
				session.scans.append(ship)
				col = Col.EASY if ship in ships_easy else Col.HARD
				logevent(f'{col}Scan{Col.END}: {ship}', '🔎', logtime)
		case 'Bounty':
			session.scans.clear()
			session.kills +=1
			thiskill = logtime
			killtime = ''
			if session.lastkill:
				seconds = (thiskill-session.lastkill).total_seconds()
				killtime = f' [+{time_format(seconds)}]'
				session.killstime += seconds
			session.lastkill = logtime
			if log_bounties:
				ship = this_json['Target_Localised'] if 'Target_Localised' in this_json else this_json['Target'].title()
				col = Col.HARD if ship in ships_hard else Col.EASY
				logevent(f'{col}Kill{Col.END}: {ship} ({this_json['VictimFaction']}){killtime}', '💥', logtime)
			if session.kills % 10 == 0 and this_json['event'] == 'Bounty':
				avgtime = time_format(session.killstime / (session.kills - 1))
				logevent(f'Session kills: {session.kills} (Avg time: {avgtime})', '📝', logtime)
		case 'MissionRedirected' if 'Mission_Massacre' in this_json['Name']:
			logevent('Completed kills for a mission', '✅', logtime)
		case 'ReservoirReplenished' if this_json['FuelMain'] < fuel_tank * 0.2:
			col = Col.BAD if this_json['FuelMain'] < fuel_tank * 0.1 else Col.WARN
			fuelremaining = round((this_json['FuelMain'] / fuel_tank) * 100)
			logevent(f'{col}Fuel reserves low!{Col.END} (Remaining: {fuelremaining}%)', '⛽', logtime)
		case 'FighterDestroyed':
			logevent(f'{Col.BAD}Fighter destroyed!{Col.END}', '🕹️', logtime)
		case 'LaunchFighter' if not this_json['PlayerControlled']:
			logevent(f'Fighter launched', '🕹️', logtime)
		case 'ShieldState':
			if this_json['ShieldsUp']: 
				shields = 'back up'
				col = Col.GOOD
			else:
				shields = 'down!'
				col = Col.BAD
			logevent(f'{col}Ship shields {shields}{Col.END}', '🛡️', logtime)
		case 'HullDamage' if this_json['Fighter'] and track.fighterhull != this_json['Health']:
			track.fighterhull = this_json['Health']
			hullhealth = round(this_json['Health'] * 100)
			logevent(f'{Col.WARN}Fighter hull damaged!{Col.END} (Health: {hullhealth}%)', '🕹️', logtime)
		case 'HullDamage' if this_json['PlayerPilot']:
			hullhealth = round(this_json['Health'] * 100)
			logevent(f'{Col.BAD}Ship hull damaged!{Col.END} (Health: {hullhealth}%)', '🛠️', logtime)
		case 'Died':
			logevent(f'{Col.BAD}Ship destroyed!{Col.END}', '💀', logtime)
		case 'Music' if this_json['MusicTrack'] == 'MainMenu':
			logevent('Exited to main menu', '📃', logtime)
		case 'Commander':
			logevent(f'Started new session for CMDR {this_json['Name']}', '🔄', logtime)
			session.reset()
		case 'SupercruiseDestinationDrop' if '$MULTIPLAYER' in this_json['Type']:
			logevent(f'Dropped at {this_json['Type_Localised']}', '🚀', logtime)
			session.reset()
		case 'ReceiveText':
			if any(x in this_json['Message'] for x in bait_messages):
				logevent(f'{Col.WARN}Pirate didn\'t engage due to insufficient cargo value{Col.END}', '🎣', logtime)
		case 'EjectCargo' if not this_json["Abandoned"]:
			name = this_json['Type_Localised'] if 'Type_Localised' else this_json['Type'].title()
			logevent(f'{Col.BAD}Cargo ejected!{Col.END} ({name})', '📦', logtime)
		case 'Shutdown':
			logevent('Quit to desktop', '🛑', logtime)
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

if __name__ == '__main__':
	# Print header
	print(f'ED AFK Monitor v{version} by CMDR PSIPAB')
	print(f'Journal folder: {journal_dir}')
	print(f'Latest journal: {journal_file}')
	print('Monitoring... (Press Ctrl+C to stop)')

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
		except KeyboardInterrupt:
			print("...Exiting by user request")
		except:
			input("Something went wrong, hit ENTER to exit")