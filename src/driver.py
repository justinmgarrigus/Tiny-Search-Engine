# This is a quick driver program that runs each function together, to simplify 
# actions for the user
import sys 
import os 
import sqlite3
from colorama import Style, Fore

from searchSuggestion import SearchSuggestion
import csv
from prepSuggestionMaster import appendPrepSuggestionMaster, searchSuggestionDriver

num_results = 5


# Prints to stderr instead of stdout. 
#   <do_color>: whether or not to color the output red. Default is True
def eprint(*args, **kwargs):
	if 'do_color' in kwargs: 
		do_color = kwargs['do_color'] 
		kwargs.pop('do_color') 
	else:
		do_color = True 

	if do_color:
		print(Fore.RED, end='', flush=True) # Flushing required here 
		
	print(*args, file=sys.stderr, **kwargs)
	
	if do_color: 
		print(Style.RESET_ALL, end='', flush=True) 


# Quits the program if the database is invalid
def check_valid_websites(cur): 
	# Make sure table was previously indexed
	command = 'SELECT name FROM sqlite_master WHERE type = "table"'
	tables = [x[0] for x in cur.execute(command).fetchall()] 
	if 'token' not in tables or 'website' not in tables: 
		eprint('Error: no index found. Index at least one valid website.') 
		sys.exit(1) 
	elif cur.execute('SELECT COUNT(*) FROM website').fetchone()[0] == 0:
		eprint('Error: no websites indexed. Index at least one valid website.')
		sys.exit(1) 


if __name__ == '__main__':
	database_file = sys.argv[-1]
	if not os.path.isfile(database_file) or database_file[-3:] != '.db': 
		eprint('Error: last argument must be a database file.')
		sys.exit(1) 
	
	# Check that the database is valid 
	con = sqlite3.connect(database_file) 
	cur = con.cursor() 
	check_valid_websites(cur) 
	
	appendPrepSuggestionMaster() 
	ss = SearchSuggestion() 
	with open('data/suggestionMaster.csv') as file_obj: 
		reader_obj = csv.reader(file_obj) 
		for row in reader_obj:
			ss.batch_insert(row)
	
	query_command = f'python3 src/index.py -q "%s" -b {database_file}'  
	name_command = f'SELECT url FROM website WHERE id = %s'
	while True: 
		query = input('Enter a query: ')
		if query.lower().strip() == 'quit': 
			break
		
		if query[-1] == '?':
			for suggestion in searchSuggestionDriver(ss, query[:-1]):
				print('  ' + suggestion)
			print()
		else: 		
			ids_str = os.popen(query_command % query).read() 
			ids = ids_str.split(';')
			
			for web_id in ids[:min(len(ids_str),num_results)]: 
				name = cur.execute(name_command % web_id).fetchone()[0]
				print('  ' + name) 
			print() 
		
	con.close() 