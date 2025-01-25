import os
import time
import json
from pathlib import Path
import argparse
import sys

# Config for events to log
config_scans = True
config_bounties = True
config_fighter = True
config_shields = True
config_hull = True

version = "250125"
ships_easy = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']
bait_messages = ['$Pirate_ThreatTooHigh', '$Pirate_NotEnoughCargo', '$Pirate_OnNoCargoFound']

class Col:
	EASY = '\x1b[38;5;157m'
	HARD = '\x1b[38;5;217m'
	WARN = '\x1b[38;5;215m'
	BAD = '\x1b[38;5;9m'
	GOOD = '\x1b[38;5;10m'
	END = '\x1b[0m'

class LogEvent:
	def __init__(self):
		self.message = ''
		self.emoji = ''

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

# Process incoming journal entries
def processline(line):
	this_json = json.loads(line)
	logmsg = LogEvent()

	match this_json['event']:
		case 'ShipTargeted' if config_scans and 'Ship' in this_json:
			ship = this_json['Ship_Localised'] if 'Ship_Localised' in this_json else this_json['Ship'].title()
			col = Col.EASY if ship in ships_easy else Col.HARD
			logmsg.emoji = '🔎'
			logmsg.message = f'{col}Scan{Col.END}: {ship}'
		case 'Bounty' if config_bounties:
			ship = this_json['Target_Localised'] if 'Target_Localised' in this_json else this_json['Target'].title()
			col = Col.EASY if ship in ships_easy else Col.HARD
			logmsg.emoji = '💥'
			logmsg.message = f'{col}Kill{Col.END}: {ship} ({this_json['VictimFaction']})'
		case 'MissionRedirected' if 'Mission_Massacre' in this_json['Name']:
			logmsg.emoji = '✔ '
			logmsg.message = 'Completed kills for a mission'
		case 'FighterDestroyed' if config_fighter:
			logmsg.emoji = '🕹 '
			logmsg.message = f'{Col.BAD}Fighter destroyed!{Col.END}'
		case 'ShieldState' if config_shields:
			if this_json['ShieldsUp']: 
				shields = 'back up'
				col = Col.GOOD
			else:
				shields = 'down!'
				col = Col.BAD
			logmsg.emoji = '🛡 '
			logmsg.message = f'{col}Ship shields are {shields}{Col.END}'
		case 'HullDamage' if config_hull and this_json['PlayerPilot']:
			hullhealth = round(this_json['Health'] * 100)
			logmsg.emoji = '⚠ '
			logmsg.message = f'{Col.BAD}Ship hull damaged!{Col.END} (Health: {hullhealth}%)'
		case 'Died':
			logmsg.emoji = '💀'
			logmsg.message = f'{Col.BAD}Ship was destroyed!{Col.END}'
		case 'Music' if this_json['MusicTrack'] == 'MainMenu':
			logmsg.emoji = '📃'
			logmsg.message = 'Exited to main menu'
		case 'Commander':
			logmsg.emoji = '🔄'
			logmsg.message = f'Started new session for CMDR {this_json['Name']}'
		case 'SupercruiseDestinationDrop' if '$MULTIPLAYER' in this_json['Type']:
			logmsg.emoji = '🚀'
			logmsg.message = f'Dropped at {this_json['Type_Localised']}'
		case 'ReceiveText':
			if any(x in this_json['Message'] for x in bait_messages):
				logmsg.emoji = '🎣'
				logmsg.message = f'{Col.WARN}Pirate didn\'t engage due to insufficient cargo value{Col.END}'
		case 'Cargo' if 'Inventory' in this_json:
			for cargo in this_json['Inventory']:
				if cargo['Stolen'] > 0:
					name = cargo['Name_Localised'] if 'Name_Localised' in cargo else cargo['Name'].title()
					logmsg.emoji = '📦'
					logmsg.message = f'{Col.BAD}Cargo stolen!{Col.END} ({name} x{cargo['Stolen']})'
		case 'Shutdown':
			logmsg.emoji = '🛑'
			logmsg.message = 'Quit to desktop'

	if logmsg.message:
		print(f'[{this_json['timestamp'][11:19]}]{logmsg.emoji} {logmsg.message}')
	if 'Quit' in logmsg.message:
		print('Terminating...')
		sys.exit()

if __name__ == '__main__':
	# Print header
	print(f'ED AFK Monitor v{version} by CMDR PSIPAB')
	print(f'Journal folder: {journal_dir}')
	print(f'Latest journal: {journal_file}')
	print('Monitoring... (Press Ctrl+C to stop)')

	# Open journal from end and watch for new lines
	with open(journal_dir+'\\'+journal_file, 'r') as file:
		file.seek(0, 2)

		while True:
			line = file.readline()
			if not line:
				time.sleep(1)
				continue
			
			processline(line)