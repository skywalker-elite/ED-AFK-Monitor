import os
import time
import json
from pathlib import Path
import argparse

# Config for events to log
config_scans = True
config_bounties = True

ships_easy = ['Adder', 'Asp Explorer', 'Asp Scout', 'Cobra Mk III', 'Cobra Mk IV', 'Diamondback Explorer', 'Diamondback Scout', 'Eagle', 'Imperial Courier', 'Imperial Eagle', 'Krait Phantom', 'Sidewinder', 'Viper Mk III', 'Viper Mk IV']

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

print('ED AFK Monitor v250124 by CMDR PSIPAB')
print('Journal folder:',journal_dir)
print('Latest journal:', journal_file)
print('Monitoring... (Press Ctrl+C to stop)')

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

# Open journal from end and watch for new lines
with open(journal_dir+'\\'+journal_file, 'r') as file:
	file.seek(0, 2)

	while True:
		line = file.readline()
		if not line:
			time.sleep(1)
			continue
		
		processline(line)
