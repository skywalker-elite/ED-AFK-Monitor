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

ships_easy = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']
bait_messages = ['$Pirate_ThreatTooHigh', '$Pirate_NotEnoughCargo', '$Pirate_OnNoCargoFound']

class Col:
	EASY = '\x1b[38;5;157m'
	HARD = '\x1b[38;5;217m'
	WARN = '\x1b[38;5;217m'
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

# Process incoming journal entries
def processline(line):
	this_json = json.loads(line)
	timestamp = '['+this_json['timestamp'][11:19]+']'
	match this_json['event']:
		case 'ShipTargeted'if config_scans and 'Ship' in this_json:
			ship = this_json['Ship_Localised'] if 'Ship_Localised' in this_json else this_json['Ship'].title()
			ship = Col.EASY+ship+Col.END if ship in ships_easy else Col.HARD+ship+Col.END
			print(timestamp+'🔎 Scan: '+ship)
		case 'Bounty' if config_bounties:
			ship = this_json['Target_Localised'] if 'Target_Localised' in this_json else this_json['Target'].title()
			ship = Col.EASY+ship+Col.END if ship in ships_easy else Col.HARD+ship+Col.END
			print(timestamp+'💥 Kill: '+ship+' ('+this_json['VictimFaction']+')')
		case 'MissionRedirected':
			if 'Mission_Massacre' in this_json['Name']:
				print(timestamp+'✔  Completed kills for a mission')
		case 'FighterDestroyed' if config_fighter:
			print(timestamp+'⚠  Fighter destroyed!')
		case 'ShieldState' if config_shields:
			shields = 'back up' if this_json['ShieldsUp'] else 'down!'
			print(timestamp+'🛡  Ship shields are '+shields)
		case 'HullDamage' if config_hull and this_json['PlayerPilot']:
			hullhealth = round(this_json['Health'] * 100)
			print(timestamp+'⚠  Ship hull damaged! Health: '+str(hullhealth)+'%')
		case 'Died':
			print(timestamp+'💀 Ship was destroyed!')
		case 'Music' if this_json['MusicTrack'] == 'MainMenu':
			print(timestamp+'📃 Exited to main menu')
		case 'Commander':
			print(timestamp+'🔄 Started new session for CMDR '+this_json['Name'])
		case 'SupercruiseDestinationDrop':
			if '$MULTIPLAYER' in this_json['Type']:
				print(timestamp+'🚀 Dropped at '+this_json['Type_Localised'])
		case 'ReceiveText':
			if any(x in this_json['Message'] for x in bait_messages):
				print(timestamp+'🎣 Pirate left due to insufficient cargo value')
		case 'Cargo' if 'Inventory' in this_json:
			for cargo in this_json['Inventory']:
				if cargo['Stolen'] > 0:
					name = cargo['Name_Localised'] if 'Name_Localised' in cargo else cargo['Name'].title()
					print(timestamp+'📦 Cargo stolen: '+name+' x'+str(cargo['Stolen']))
		case 'Shutdown':
			print(timestamp+'🛑 Quit to desktop')
			print('Terminating...')
			sys.exit()

if __name__ == '__main__':
	# Print header
	print('ED AFK Monitor v250124 by CMDR PSIPAB')
	print('Journal folder:',journal_dir)
	print('Latest journal:', journal_file)
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