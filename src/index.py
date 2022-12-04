import sys 
import re
import sqlite3 
import getopt 
import json 
import math 
import socket 
import os 
import io 
import urllib 
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from colorama import Fore, Style
from collections import defaultdict
import unittest 
import unittest.mock 
from parameterized import parameterized 

import nltk 
from nltk.stem import PorterStemmer
nltk.download('stopwords', quiet=True) 
from nltk.corpus import stopwords

import hashlib
def stem_to_int(stem): 
	return int(hashlib.sha1(bytes(stem, 'utf-8')).hexdigest(), 16) % 1000000000


default_database_file = 'data/table.db' 
null_database_file = 'data/null.db' 

usage = f'''\
Usage: 
    python3 index.py {{-w <website> | -q <query> | -d <document>}} [-t <timeout] 
        [-b <database>] [--verbose]

Options: 
    <website>: (string) Name of a website or file containing a line-separated
        list of names of websites. Indexes content of site(s) into the database.
    <query>: (string) Query written in plain English. Yields a string
        representing a semicolon-separated list of website indices, relative to
        the database. 
    <document>: (string) For debugging purposes, a document to be indexed
        directly instead of a website pointing to a document. 
    <timeout>: (positive float) How long to wait for a response from a server 
        before exiting. Default is 5 seconds. 
    <database>: (string) File to read/write database information. Default is 
        "{default_database_file}". If "null", saves to "{null_database_file}" 
        and deletes after.
    verbose: Prints extra debug information to stdout.
'''


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
def scrape_text(reference, timeout, verbose): 
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
			html_page = urlopen(req, timeout=timeout)
			
			soup = BeautifulSoup(html_page, 'html.parser') 
			all_text = soup.findAll(text=True)
			text = u" ".join(t.strip() for t in all_text)
		except Exception as ex: 
			text = None
			print(Fore.YELLOW + f'Failed ({ex})' + Style.RESET_ALL)
		
	if verbose:  
		if text is not None: 
			print(Fore.CYAN + 'Obtained' + Style.RESET_ALL) 
	
	return text 


# Takes the collection of words pointed to by <reference, str> and stores it 
# into the database.
def process_document(cur, database_name, reference, stop_words, stemmer, \
                     timeout, verbose):
	reference = reference.strip()
	text_str = scrape_text(reference, timeout, verbose) 
	if text_str is None:
		return 

	# Words we will index 
	stems = get_stem_dict(text_str, stop_words, stemmer) 
	
	if verbose: 
		message = f'Inserting {len(stems)} stems into {database_name} ... '
		print(message, flush=True, end='')
	
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
		
	if verbose: 
		print(Fore.CYAN + 'Done' + Style.RESET_ALL)


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
		
	
def query_websites(cur, query, stop_words, stemmer, verbose):
	check_valid_websites(cur) 
	
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
		
		websites.append((name, term_sum, website))
	
	websites = sorted(websites, key=lambda x: x[1], reverse=True)
	
	if len(websites) > 0: 
		for website in websites[:-1]: 
			print(website[2], end=';')
		print(websites[-1][2])
		
		if verbose:
			for website in websites[:10]:
				print('[%.3f] %s' % (website[1], website[0]))
	
	
def main(args): 
	# For ease of testing, this turns command-line arguments passed as a string
	# into something more traditionally used with sys.argv
	if isinstance(args, str): 
		args = re.findall(r'("[^"]+"|[^\s"]+)', args)
		args = [
			arg[1:-1] if arg[0] == arg[-1] and arg[0] in ('\'', '"')
			else arg for arg in args 
		]

	# Iterate through arguments 
	try:
		short = 'w:q:t:d:b:'
		long = ['verbose'] 
		iterator = getopt.gnu_getopt(args, short, long)[0] 
	except getopt.GetoptError as ex: 
		eprint(f'Error: unrecognized argument specified "{ex.opt}"\n') 
		eprint(usage, do_color=False) 
		sys.exit(1) 
	
	website = None 
	query = None 
	document = None 
	timeout = None 
	database = None 
	verbose = None
	for option, value in iterator: 
		if option == '-w': 
			if website is not None: 
				eprint('Error: only one argument can specify a website\n')
				eprint(usage, do_color=False) 
				sys.exit(1) 
			
			website = value 
		
		elif option == '-q': 
			if query is not None: 
				eprint('Error: only one argument can specify a query\n')
				eprint(usage, do_color=False) 
				sys.exit(1)
			
			query = value 
			
		elif option == '-d':
			if document is not None: 
				eprint('Error: only one argument can specify a document\n') 
				eprint(usage, do_color=False) 
				sys.exit(1) 
			
			document = value 
			
		elif option == '-b':
			if database is not None: 
				eprint('Error: only one argument can specify a database\n') 
				eprint(usage, do_color=False) 
				sys.exit(1) 
			
			database = value 
			
		elif option == '-t':
			if timeout is not None: 
				message =  'Error: only one argument can specify a timeout '
				message += 'amount\n' 
				eprint(message) 
				eprint(usage, do_color=False) 
				sys.exit(1) 
			
			try: 
				timeout = float(value) 
			except ValueError: 
				message = 'Error: timeout amount must be numeric and '
				message += 'positive, "' + str(value) + '" found\n'
				eprint(message) 
				eprint(usage, do_color=False) 
				sys.exit(1) 
				
			if timeout <= 0: 
				message = 'Error: timeout amount must be positive, "'
				message += str(value) + '" found\n'
				eprint(message) 
				eprint(usage, do_color=False) 
				sys.exit(1) 
			
		elif option == '--verbose': 
			verbose = True 
		
		else:
			eprint(f'Error: unrecognized argument specified "{ex.opt}"\n') 
			eprint(usage, do_color=False) 
			sys.exit(1) 
	
	# Default values 
	if timeout is None: timeout = 5 
	if verbose is None: verbose = False 
	
	if database is None: database = default_database_file
	elif database.lower() == 'null': database = null_database_file
	
	given_elements = sum(x is not None for x in (website, query, document))
	if given_elements > 1: 
		message =  'Error: only one of the options among (-w, -q, -d) can be '
		message += 'provided at a single time'
		eprint(message) 
		eprint(usage, do_color=False) 
		sys.exit(1)
	
	if given_elements == 0: 
		message =  'Error: either the website (-w), query (-q), or ' 
		message += 'document (-d) flags must be present\n'
		eprint(message) 
		eprint(usage, do_color=False)  
		sys.exit(1) 
		
	stop_words = set(stopwords.words('english'))
	stemmer = PorterStemmer() 
	
	if query is not None and not os.path.isfile(database): 
		# User wants to query from a database that doesn't exist. 
		eprint('Error: no index found. Index at least one valid website.')
		sys.exit(1) 
	
	# Open connection to the database
	con = sqlite3.connect(database)
	cur = con.cursor()
	
	if query is not None: 
		query_websites(cur, query, stop_words, stemmer, verbose) 
	
	elif website is not None: 
		# Interpret the website as a file to a line-separated list of websites. 
		try: 
			website_file = open(website, 'r') 
			for website in website_file.readlines():
				process_document(cur, database, website, stop_words, stemmer, \
				                 timeout, verbose)
			website_file.close() 
		except OSError: 
			# If the open statement failed, then interpret it as a plain website
			# instead. 
			process_document(cur, database, website, stop_words, stemmer, \
			                 timeout, verbose)
			
	elif document is not None: 
		process_document(cur, database, document, stop_words, stemmer, \
		                 timeout, verbose)
						 
	if document is not None or website is not None:
		check_valid_websites(cur) 
		website_size = cur.execute('SELECT COUNT(*) FROM website').fetchone()[0]
		tokens_size = cur.execute('SELECT COUNT(*) FROM token').fetchone()[0]
		print('Table(website) size:', website_size) 
		print('Table(token) size:', tokens_size) 
	
	con.commit()
	con.close() 
	
	if database == null_database_file:
		os.system('rm ' + null_database_file) 


# Boilerplate tests that verify command-line arguments, where the key is the
# name of the test and the value is the arguments supplied.
cla_tests = {                                                                  \
'no_args':                                                                     \
	'index.py',                                                                \
'no_main_direction':                                                           \
	'index.py -t 5 -b output.txt',                                             \
'multiple_main_direction':                                                     \
	'index.py -w "http://example.com/" -q test',                               \
'unknown_single_option_1':                                                     \
	'index.py -z',                                                             \
'unknown_single_option_2':                                                     \
	'index.py --z',                                                            \
'unknown_double_option':                                                       \
	'index.py -z test',                                                        \
'missing_document':                                                            \
	'index.py -d "data/this-file-should-not-exist.txt"',                       \
'missing_database':                                                            \
	'index.py -q test -b data/this-database-should-not-exist.txt',             \
'timeout_not_numeric':                                                         \
	'index.py -w "http://example.com/" -t test',                               \
'timeout_negative':                                                            \
	'index.py -w "http://example.com/" -t -3.14',                              \
'multiple_website_specified':                                                  \
	'index.py -w "http://example.com/" -w "http://example.com/"',              \
'multiple_query_specified':                                                    \
	'index.py -q "test" -q "test"',                                            \
'multiple_document_specified':                                                 \
	'index.py -d "data/document-1.txt" -d "data/document-2.txt"',              \
'multiple_database_specified':                                                 \
	'index.py -w "http://example.com/" -b "null" -b "null"',                   \
'multiple_timeout_specified':                                                  \
	'index.py -w "http://example.com/" -t 5 -t 10',                            \
'verbose_misspelled':                                                          \
	'index.py -w "http://example.com/" --verbosee'                             \
}


# Collection of simple tests that should all return SystemExit signals (due to
# sys.exit(1) calls) due to poor formatting of the command-line arguments. 
class CommandLineArgumentTest(unittest.TestCase):
	# Runs each test case in cla_tests
	@parameterized.expand(cla_tests.items())
	def test_cla(self, name, args): 
		with self.assertRaises(SystemExit) as cm: 
			main(args)


# Collection of more complicated tests that have internal logic in them. 
class UniqueTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls): 
		cls.test_table = 'data/unit-test-table.db'
	
	
	@classmethod
	def remove_test_table(cls):
		os.system('rm -f ' + cls.test_table)
		
		
	@classmethod
	def tearDownClass(cls):
		cls.remove_test_table()
	
	
	# Test that a null database does not create a table at the default location
	def test_null_database(self): 
		args = 'index.py -w "https://example.com/" -b null'
		main(args)
		self.assertFalse(os.path.isfile(null_database_file))
	
	
	# Test that websites will correctly timeout
	def test_timeout(self):
		args = 'index.py -w "http://example.com/" -t 0.0001 -b null --verbose'
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			try:
				main(args)
				self.fail('No exception raised for empty database')
			except SystemExit as ex: 
				message = 'Network is unreachable' 
				self.assertRegex(fake_out.getvalue(), message)
		
		
	# Test that the size of the database changes after each indexing of a 
	# document
	def test_document_database_increase(self): 
		args = 'index.py -d "%s" -b ' + self.test_table 
		doc_1 = 'data/documents/information-processing.txt' 
		doc_2 = 'data/documents/nintendogs.txt' 
		website_regex = r'Table\(website\) size: ([0-9]+)'
		token_regex = r'Table\(token\) size: ([0-9]+)'
		
		self.remove_test_table()
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(args % doc_1)
			out = fake_out.getvalue()
			start_website_size = re.search(website_regex, out).group(1)
			start_token_size = re.search(token_regex, out).group(1)
			
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out: 
			main(args % doc_2)
			out = fake_out.getvalue() 
			end_website_size = re.search(website_regex, out).group(1)
			end_token_size = re.search(token_regex, out).group(1)
					
		try: 
			start_website_size = int(start_website_size) 
			start_token_size = int(start_token_size) 
			end_website_size = int(end_website_size) 
			end_token_size = int(end_token_size) 
		except ValueError: 
			self.fail('Website/token regex did not match')
			
		self.assertGreater(end_website_size, start_website_size) 
		self.assertGreater(end_token_size, start_token_size)


	# Test that a website-collection that contains both unique websites and 
	# unique documents are each indexed. 
	def test_index_document_multi(self): 
		args = 'index.py -w "data/links/multi-document.txt" -b null' 
		website_regex = r'Table\(website\) size: ([0-9]+)'
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out: 
			main(args)
			out = fake_out.getvalue() 
			website_size = re.search(website_regex, out).group(1) 
			self.assertEquals(website_size, '3') # 3 docs in collection 


	# Test that the size of the database changes after each indexing of a 
	# website
	def test_website_database_increase(self): 
		args = 'index.py -w "%s" -b ' + self.test_table 
		link_1 = 'https://en.wikipedia.org/wiki/Computer_science' 
		link_2 = 'https://en.wikipedia.org/wiki/Nintendogs' 
		website_regex = r'Table\(website\) size: ([0-9]+)'
		token_regex = r'Table\(token\) size: ([0-9]+)'
		
		self.remove_test_table()
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(args % link_1)
			out = fake_out.getvalue()
			start_website_size = re.search(website_regex, out).group(1)
			start_token_size = re.search(token_regex, out).group(1)
			
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out: 
			main(args % link_2)
			out = fake_out.getvalue() 
			end_website_size = re.search(website_regex, out).group(1)
			end_token_size = re.search(token_regex, out).group(1)
					
		try: 
			start_website_size = int(start_website_size) 
			start_token_size = int(start_token_size) 
			end_website_size = int(end_website_size) 
			end_token_size = int(end_token_size) 
		except ValueError: 
			self.fail('Website/token regex did not match')
			
		self.assertGreater(end_website_size, start_website_size) 
		self.assertGreater(end_token_size, start_token_size)
	
	
	# Tests that a query returns the expected documents
	def test_document_query(self): 
		insert_args = 'index.py -d "%s" -b ' + self.test_table 
		query_args = 'index.py -q "%s" -b ' + self.test_table
		doc_1 = 'data/documents/information-processing.txt'
		doc_2 = 'data/documents/nintendogs.txt'
		doc_1_unique_query = 'telecommunications' 
		doc_2_unique_query = 'dog' 
		doc_general_query = 'microphone'
		website_regex = r'Table\(website\) size: ([0-9]+)'
		
		self.remove_test_table() 
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(insert_args % doc_1) 
			out = fake_out.getvalue() 
			doc_1_index = re.search(website_regex, out).group(1)
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(insert_args % doc_2) 
			out = fake_out.getvalue() 
			doc_2_index = re.search(website_regex, out).group(1)
			
		try: 
			doc_1_index = str(int(doc_1_index) - 1)
			doc_2_index = str(int(doc_2_index) - 1)
		except ValueError: 
			self.fail('Website/token regex did not match')
			
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_1_unique_query)
			out = fake_out.getvalue().strip()
			self.assertTrue(doc_1_index in out.split(';'))
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_2_unique_query) 
			out = fake_out.getvalue().strip() 
			self.assertTrue(doc_2_index in out.split(';'))
			
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_general_query) 
			out = fake_out.getvalue().strip()
			indices = out.split(';') 
			self.assertTrue(doc_1_index in indices and doc_2_index in indices)
	
	
	# Tests that documents are ranked in the correct order given single-word 
	# queries
	def test_document_rank_single(self): 
		insert_args = 'index.py -d "%s" -b ' + self.test_table 
		query_args = 'index.py -q "%s" -b ' + self.test_table
		doc_1 = 'data/documents/information-processing.txt'
		doc_2 = 'data/documents/nintendogs.txt'
		doc_1_relevancy_query = 'information'
		doc_2_relevancy_query = 'microphone'
		website_regex = r'Table\(website\) size: ([0-9]+)'
		
		self.remove_test_table() 
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(insert_args % doc_1) 
			out = fake_out.getvalue() 
			doc_1_index = re.search(website_regex, out).group(1)
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(insert_args % doc_2) 
			out = fake_out.getvalue()
			doc_2_index = re.search(website_regex, out).group(1)
		
		try: 
			doc_1_index = str(int(doc_1_index) - 1)
			doc_2_index = str(int(doc_2_index) - 1)
		except ValueError: 
			self.fail('Website/token regex did not match')
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_1_relevancy_query)
			out = fake_out.getvalue().strip()
			indices = out.split(';') 
			self.assertTrue(doc_1_index in indices and doc_2_index in indices)
			self.assertLess(out.index(doc_1_index), out.index(doc_2_index)) 
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_2_relevancy_query)
			out = fake_out.getvalue().strip() 
			indices = out.split(';') 
			self.assertTrue(doc_1_index in indices and doc_2_index in indices)
			self.assertLess(out.index(doc_2_index), out.index(doc_1_index))
			
			
	# Tests that documents are ranked in the correct order given multi-word 
	# queries
	def test_document_rank_multi(self): 
		insert_args = 'index.py -d "%s" -b ' + self.test_table 
		query_args = 'index.py -q "%s" -b ' + self.test_table
		doc_1 = 'data/documents/information-processing.txt'
		doc_2 = 'data/documents/nintendogs.txt'
		doc_1_relevancy_query = 'what is the study of information and algorithm'
		doc_2_relevancy_query = 'what information gets me better dogs'
		website_regex = r'Table\(website\) size: ([0-9]+)'
		
		self.remove_test_table() 
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(insert_args % doc_1) 
			out = fake_out.getvalue() 
			doc_1_index = re.search(website_regex, out).group(1)
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(insert_args % doc_2) 
			out = fake_out.getvalue()
			doc_2_index = re.search(website_regex, out).group(1)
		
		try: 
			doc_1_index = str(int(doc_1_index) - 1)
			doc_2_index = str(int(doc_2_index) - 1)
		except ValueError: 
			self.fail('Website/token regex did not match')
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_1_relevancy_query)
			out = fake_out.getvalue().strip()
			indices = out.split(';') 
			self.assertTrue(doc_1_index in indices and doc_2_index in indices)
			self.assertLess(out.index(doc_1_index), out.index(doc_2_index)) 
		
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(query_args % doc_2_relevancy_query)
			out = fake_out.getvalue().strip() 
			indices = out.split(';') 
			self.assertTrue(doc_1_index in indices and doc_2_index in indices)
			self.assertLess(out.index(doc_2_index), out.index(doc_1_index))
	

if __name__ == '__main__': 
	main(sys.argv) 