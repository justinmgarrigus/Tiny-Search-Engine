import sys 
import re 
import enchant 
import sqlite3 
import getopt 
import json 
import math 
from bs4 import BeautifulSoup 
from urllib.request import Request, urlopen
from colorama import Fore, Style
from gen import eprint
from collections import defaultdict

import nltk 
from nltk.stem import PorterStemmer
nltk.download('stopwords', quiet=True) 
from nltk.corpus import stopwords

import hashlib
def stem_to_int(stem): 
	return int(hashlib.sha1(bytes(stem, 'utf-8')).hexdigest(), 16) % 1000000000


def website_create_table(cur): 
	command = 'CREATE TABLE IF NOT EXISTS website(' \
	          'id INTEGER PRIMARY KEY, '            \
			  'url TEXT UNIQUE, '                   \
			  'm INTEGER, '                         \
			  'data TEXT)'
	cur.execute(command) 


# Inserts the website into the database and returns the primary key it was 
# assigned (or None if this website already existed in the table) 
def website_insert(cur, url, stems):
	# If this url already exists in the table, exit. 
	command = f'SELECT id FROM website WHERE url = "{url}"'
	existing_id = cur.execute(command).fetchone()  
	already_exists = cur.execute(command).fetchone() != None 
	if already_exists:
		return None 
		
	size = cur.execute('SELECT COUNT(*) FROM website').fetchone()[0]
	m = max(stems.values()) 
	data = ','.join(key + ':' + str(value) for key, value in stems.items())
	
	command = f'INSERT INTO website VALUES({size}, "{url}", {m}, "{data}")'
	cur.execute(command) 
	return size 
	

def token_create_table(cur): 
	command = 'CREATE TABLE IF NOT EXISTS token('
	command +=  'stem INTEGER PRIMARY KEY, '
	command +=  'doc TEXT)' # TODO: see if BLOB is better
	cur.execute(command) 
	

def token_insert(cur, stem, website_id): 
	stem = stem_to_int(stem) 
	command = f'SELECT doc FROM token WHERE stem = {stem}'
	doc = cur.execute(command).fetchone()
	
	if doc is None: 
		# The stem has not yet been added to the table, so we can be the first 
		# addition 
		# TODO: 'replace' should not be necessary here, so why is it?
		command = 'INSERT OR REPLACE INTO token VALUES(' 
		command += f'{stem}, "{website_id}")'  
	else: 
		# The stem has been added before, so append our website_id to the end 
		text = doc[0] + ';' + str(website_id) 
		command = f'UPDATE token SET doc = "{text}" WHERE stem = "{stem}"'
	
	cur.execute(command)


# Return a dictionary of unique strings (not including stopwords) that appear in 
# the text. These strings are made up of only lowercase alphabetic characters. 
# The keys are stems, the values are frequencies (int) 
def get_stem_dict(text, stop_words, stemmer): 
	# Go through each collection of words (where a "word" is considered to be 
	# alphabetic characters grouped together). 
	stems = defaultdict(lambda: 0) 
	for m in re.finditer(r'[a-zA-Z]+', text):
		word = m.group(0).lower()
		stem = stemmer.stem(word)  
		if stem not in stop_words: 
			stems[stem] += 1 
	
	return stems 


# Scrapes the text from the reference (either the name of a file containing 
# plain text or the hyperlink to a website with content). Returns either None 
# if the file cannot be opened or the content of the document. 
def scrape_text(reference, verbose): 
	if verbose: 
		print(f'Reading "{reference}" ... ', flush=True, end='') 
	
	try:
		# Interpret the reference as a file name first 
		doc_file = open(reference, 'r') 
		text = doc_file.read()
		doc_file.close()
	except OSError: 
		# Interpret it as a website 
		try: 
			req = Request(reference)
			html_page = urlopen(req)
			
			soup = BeautifulSoup(html_page, 'html.parser') 
			all_text = soup.findAll(text=True)
			text = u" ".join(t.strip() for t in all_text)
		except Exception as ex: 
			text = None
			if text is None: 
				print(Fore.YELLOW + f'Failed ({type(ex)})' + Style.RESET_ALL)
		
	if verbose:  
		if text is not None: 
			print(Fore.CYAN + 'Obtained' + Style.RESET_ALL) 
	
	return text 


# Takes the collection of words pointed to by <reference, str> and stores it 
# into the database.
def process_document(reference, stop_words, stemmer, verbose): 	
	reference = reference.strip()
	text_str = scrape_text(reference, verbose) 
	if text_str is None:
		return 

	# Words we will index 
	stems = get_stem_dict(text_str, stop_words, stemmer) 
	
	if verbose: 
		message = f'Inserting {len(stems)} stems into table.db ... '
		print(message, flush=True, end='')
	
	# Open the connection to the database 
	con = sqlite3.connect('table.db') 
	cur = con.cursor()
	
	# Optionally create table and insert this reference into it.
	website_create_table(cur) 
	website_id = website_insert(cur, reference, stems) 
	if website_id == None:
		if verbose: 
			print(Fore.YELLOW + 'Failed (duplicate entry)' + Style.RESET_ALL)
		return # Nothing new to do, already indexed 
	
	token_create_table(cur) 
	for stem in stems.keys():
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
	
	stems = get_stem_dict(query, stop_words, stemmer)
	for stem in stems.keys(): 
		stem = stem_to_int(stem) 
		command = f'SELECT doc FROM token WHERE stem = {stem}' 
		websites = cur.execute(command).fetchone()
		if websites is not None: 
			for website in websites: 
				website_set.update(website.split(';')) 
	
	website_count = cur.execute('SELECT COUNT(*) FROM website').fetchone()[0]
	websites = [] 
	for website in website_set: 
		name = cur.execute(f'SELECT url FROM website WHERE id = {website}').fetchone()[0] 
		
		command = f'SELECT m, data FROM website WHERE id = {website}'
		m, freq_data = cur.execute(command).fetchone() 
		
		term_sum = 0
		for item in freq_data.split(','): 
			parts = item.split(':') 
			if parts[0] in stems.keys(): 
				command = f'SELECT doc FROM token WHERE stem = {stem_to_int(parts[0])}'
				term_count = cur.execute(command).fetchone()[0].count(':') + 1 
				tf_ij = int(parts[1]) / m 
				idf_i = math.log2(website_count / term_count) + 1  
				term_sum += tf_ij * idf_i 
		
		websites.append((name, term_sum))
		
	websites = sorted(websites, key=lambda x: x[1], reverse=True)
	for website in websites[:10]:
		print('[%.3f] %s' % (website[1], website[0]))
	
	
def print_usage(): 
	pass 


def main(args): 
	# Iterate through arguments 
	try:
		short = 'w:q:t:d:'
		long = ['verbose'] 
		iterator = getopt.gnu_getopt(args, short, long)[0] 
	except getopt.GetoptError as ex: 
		eprint(f'Error: unrecognized argument specified "{ex.opt}"\n') 
		print_usage() 
		sys.exit(1) 
	
	website = None 
	query = None 
	document = None 
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
			
		elif option == '-d':
			if document is not None: 
				eprint('Error: only one argument can specify a document\n') 
				print_usage() 
				sys.exit(1) 
			
			document = value 
			
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
	
	none_elems = sum(x is not None for x in (website, query, document))
	if none_elems > 1: 
		message =  'Error: only one of the options among (-w, -q, -d) can be '
		message += 'provided at a single time'
		eprint(message) 
		print_usage() 
		sys.exit(1)
	
	if none_elems == 0: 
		message =  'Error: either the website (-w), query (-q), or ', 
		message += 'document (-d) flags must be present\n'
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
				process_document(website, stop_words, stemmer, verbose)
			website_file.close() 
		except OSError: 
			# If the open statement failed, then interpret it as a plain website
			# instead. 
			process_document(website, stop_words, stemmer, verbose)
			
	elif document is not None: 
		process_document(document, stop_words, stemmer, verbose)
		

if __name__ == '__main__': 
	main(sys.argv) 