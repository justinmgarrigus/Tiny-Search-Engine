import sys 
import re 
import enchant 
import sqlite3 
import getopt 
from bs4 import BeautifulSoup 
from urllib.request import Request, urlopen
from colorama import Fore, Style
from gen import eprint

import nltk 
from nltk.stem import PorterStemmer
nltk.download('stopwords', quiet=True) 
from nltk.corpus import stopwords


def website_create_table(cur): 
	command = 'CREATE TABLE IF NOT EXISTS website('
	command +=  'id INTEGER PRIMARY KEY, '
	command +=  'url TEXT UNIQUE)'
	cur.execute(command) 


# Inserts the website into the database and returns the primary key it was 
# assigned (or None if this website already existed in the table) 
def website_insert(cur, url):
	# If this url already exists in the table, exit. 
	command = f'SELECT id FROM website WHERE url = "{url}"'
	existing_id = cur.execute(command).fetchone()  
	already_exists = cur.execute(command).fetchone() != None 
	if already_exists:
		return None 
	
	size = cur.execute('SELECT COUNT(*) FROM website').fetchone()[0]
	command = f'INSERT INTO website VALUES({str(size)}, "{url}")'
	cur.execute(command) 
	return size 
	

def token_create_table(cur): 
	command = 'CREATE TABLE IF NOT EXISTS token('
	command +=  'stem TEXT PRIMARY KEY, '
	command +=  'doc TEXT)' # TODO: see if BLOB is better
	cur.execute(command) 
	

def token_insert(cur, stem, website_id): 
	command = f'SELECT doc FROM token WHERE stem = "{stem}"'
	doc = cur.execute(command).fetchone()
	
	if doc is None: 
		# The stem has not yet been added to the table, so we can be the first 
		# addition 
		# TODO: 'replace' should not be necessary here, so why is it?
		command = 'INSERT OR REPLACE INTO token VALUES(' 
		command += f'"{stem}", "{website_id}")'  
	else: 
		# The stem has been added before, so append our website_id to the end 
		text = doc[0] + ';' + str(website_id) 
		command = f'UPDATE token SET doc = "{text}" WHERE stem = "{stem}"'
	
	cur.execute(command)


# Return a set of unique strings (not including stopwords) that appear in the
# text. These strings are made up of only lowercase alphabetic characters. 
def get_stem_set(text, stop_words, stemmer): 
	# Go through each collection of words (where a "word" is considered to be 
	# alphabetic characters grouped together). 
	stem_set = set() 
	for m in re.finditer(r'[a-zA-Z]+', text):
		word = m.group(0).lower()
		stem = stemmer.stem(word) 
		stem_set.add(stem)  
	
	# Remove stop words from the set
	return stem_set.difference(stop_words) 


# Takes the given hyperlink, scrapes the text from it, and stores it into the 
# database. 
def process_website(hyperlink, stop_words, stemmer, verbose): 
	if verbose: 
		print(f'Reading "{hyperlink}" ... ', flush=True, end='') 

	try: 
		req = Request(hyperlink)
		html_page = urlopen(req) 
	except Exception as ex: 
		if verbose:  
			print(Fore.YELLOW + f'Failed({type(ex)})' + Style.RESET_ALL)
		return 
	
	soup = BeautifulSoup(html_page, 'html.parser') 
	all_text = soup.findAll(text=True)
	text_str = u" ".join(t.strip() for t in all_text)
	
	if verbose:
		print(Fore.CYAN + 'Obtained' + Style.RESET_ALL) 
	
	# Words we will index 
	stem_set = get_stem_set(text_str, stop_words, stemmer) 
	
	if verbose: 
		message = f'Inserting {len(stem_set)} stems into table.db ... '
		print(message, flush=True, end='')
	
	# Open the connection to the database 
	con = sqlite3.connect('table.db') 
	cur = con.cursor()
	
	# Optionally create table and insert this hyperlink into it.
	website_create_table(cur) 
	website_id = website_insert(cur, hyperlink) 
	if website_id == None:
		if verbose: 
			print(Fore.YELLOW + 'Failed (duplicate entry)' + Style.RESET_ALL)
		return # Nothing new to do, already indexed 
	
	token_create_table(cur) 
	for stem in stem_set:
		token_insert(cur, stem, website_id); 
	
	con.commit()
	if verbose: 
		print(Fore.CYAN + 'Success' + Style.RESET_ALL) 
		website_size = cur.execute('SELECT COUNT(*) FROM website').fetchone()[0]
		tokens_size = cur.execute('SELECT COUNT(*) FROM token').fetchone()[0]
		print('  Table(website) size:', website_size) 
		print('  Table(token) size:', tokens_size)
		
	
def query_websites(query, stop_words, stemmer, verbose): 
	# Open the connection to the database 
	con = sqlite3.connect('table.db') 
	cur = con.cursor()
	
	website_set = set() 
	
	stem_set = get_stem_set(query, stop_words, stemmer)
	for stem in stem_set: 
		command = f'SELECT doc FROM token WHERE stem = "{stem}"' 
		websites = cur.execute(command).fetchone()
		if websites is not None: 
			for website in websites: 
				website_set.update(website.split(';')) 
	
	for website in website_set: 
		name = cur.execute(f'SELECT url FROM website WHERE id = {website}').fetchone()[0] 
		print(website, name) 
	
	
def print_usage(): 
	pass 


def main(args): 
	# Iterate through arguments 
	try:
		short = 'w:q:t:'
		long = ['verbose'] 
		iterator = getopt.gnu_getopt(args, short, long)[0] 
	except getopt.GetoptError as ex: 
		eprint(f'Error: unrecognized argument specified "{ex.opt}"\n') 
		print_usage() 
		sys.exit(1) 
	
	website = None 
	query = None 
	timeout = None 
	verbose = None
	for option, value in iterator: 
		if option == '-w': 
			if website is not None: 
				eprint('Error: only one argument can specify a website\n')
				print_usage() 
				sys.exit(1) 
			
			website = value 
		
		elif option == '-q': 
			if query is not None: 
				eprint('Error: only one argument can specify a query\n')
				print_usage() 
				sys.exit(1)
			
			query = value 
			
		elif option == '-t':
			if timeout is not None: 
				message =  'Error: only one argument can specify a timeout '
				message += 'amount\n' 
				eprint(message) 
				print_usage() 
				sys.exit(1) 
			
			try: 
				timeout = float(value) 
			except ValueError: 
				message = 'Error: timeout amount must be numeric and '
				message += 'positive, "' + str(value) + '" found\n'
				eprint(message) 
				print_usage() 
				sys.exit(1) 
				
			if timeout <= 0: 
				message = 'Error: timeout amount must be positive, "'
				message += str(value) + '" found\n'
				eprint(message) 
				print_usage() 
				sys.exit(1) 
			
		elif option == '--verbose': 
			verbose = True 
		
		else:
			eprint(f'Error: unrecognized argument specified "{ex.opt}"\n') 
			print_usage() 
			sys.exit(1) 
	
	# Default values 
	if timeout is None: timeout = 5 
	if verbose is None: verbose = False 
	
	if query is not None and website is not None: 
		message = 'Error: the website (-w) and query (-q) flags cannot '
		message += 'both be provided at the same time\n' 
		eprint(message) 
		print_usage() 
		sys.exit(1)
	
	if query is None and website is None: 
		message = 'Error: either the website (-w) or the query (-q) flags must '
		message += 'be present\n'
		eprint(message) 
		print_usage() 
		sys.exit(1) 
		
	stop_words = set(stopwords.words('english'))
	stemmer = PorterStemmer() 
	
	if query is not None: 
		query_websites(query, stop_words, stemmer, verbose) 
	
	elif website is not None: 
		# Interpret the website as a file to a line-separated list of websites. 
		try: 
			website_file = open(website, 'r') 
			for website in website_file.readlines():
				process_website(website.strip(), stop_words, stemmer, verbose) 
		except OSError: 
			# If the open statement failed, then interpret it as a plain website
			# instead. 
			process_website(website, stop_words, stemmer, True)


if __name__ == '__main__': 
	main(sys.argv) 