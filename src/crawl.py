import sys 
import os 
import io 
import getopt 
import re
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import socket 
from colorama import Fore, Style
import unittest 
import unittest.mock 
from parameterized import parameterized 


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


class CircularQueue: 
	class _CircularQueueIterator: 
		def __init__(self, coll):
			self._coll = coll 
			self._index = 0 
		
		
		def __next__(self): 
			if self._index < len(self._coll): 
				value = self._coll._queue[self._index] 
				self._index += 1 
				return value 
			else:
				raise StopIteration 
	
	
	def __init__(self, length): 
		self._queue = [None] * length
		self._items = set()
		self._start_index = 0 
		self._end_index = 0
	
	
	def __iter__(self):
		return CircularQueue._CircularQueueIterator(self)
		
	
	# Inserts <value> to the end of the queue. 
	def insert(self, value): 
		assert self._end_index < len(self._queue)		
		
		self._queue[self._end_index] = value 
		self._end_index += 1 
		self._items.add(value) 
		
	
	# Returns the item at the beginning of the queue and advances the start 
	# pointer to the next spot. 
	def poll(self):
		assert not self.is_limit() 
		
		value = self._queue[self._start_index] 
		self._start_index += 1 
		return value 
		
	
	# Returns true if we cannot add any more elements to the queue. 
	def is_full(self):
		return self._end_index == len(self._queue)
		
		
	# Returns true if we cannot poll any more. 
	def is_limit(self): 
		return self._start_index >= self._end_index 
		
	
	def __str__(self):
		result = '[' 
		for value in self:
			result += str(value) + ', ' 
		return result[:-2] + ']' # Remove last comma and space 
		
	
	# Returns how many times insert() was invoked. 
	def __len__(self): 
		return self._end_index 
		
		
	# Returns true if <item> exists somewhere inside the queue. 
	def __contains__(self, item): 
		return item in self._items 


# Takes the website at the start of the queue, scrapes the hyperlinks found on
# it, and adds each hyperlink to the end of the queue. 
def process_website(queue, verbose, timeout, validate): 
	assert not queue.is_full()
	
	# Contains rules for 'valid' hyperlinks, returns True if the link is valid. 
	# Some links may be incomplete (as in they only contain the URL's path), 
	# but incomplete links will still be marked as valid in this case. 
	def is_valid(hyperlink): 
		return                        \
			hyperlink is not None and \
			len(hyperlink) > 0    and \
			hyperlink[0] != '#'   and \
			'<' not in hyperlink  and \
			'"' not in hyperlink 
	
	url = queue.poll()
	if verbose: print('Reading: "', url, '" ... ', sep='', end='', flush=True) 
	try: 
		req = Request(url) 
		html_page = urlopen(req, timeout=timeout) 
	except Exception as ex: 
		if verbose: 
			message = f'{type(ex)}, {ex.reason}' 
			print(Fore.YELLOW + f'Failed ({message})' + Style.RESET_ALL) 
		return 
	soup = BeautifulSoup(html_page, 'html.parser') 
	if verbose: print(Fore.CYAN + 'Obtained' + Style.RESET_ALL)
	
	# In the example "https://en.wikipedia.org/wiki/Computer_science", the
	# domain is "https://en.wikipedia.org". It is located by the first '/' after
	# the first '//'.
	domain = url[:url.index('/', url.index('//')+2)]
	
	for link in soup.find_all('a'):
		hyperlink = link.get('href')
		if is_valid(hyperlink): 
			if hyperlink.find('//') <= 0: # Doesn't exist or is in first spot
				hyperlink = domain + hyperlink 		
			
			if hyperlink in queue:
				continue 
			
			if validate: 
				try: 
					validate_request = Request(hyperlink) 
					urlopen(validate_request, timeout=timeout)
				except Exception as ex: 
					if verbose: 
						message =  f'{Fore.YELLOW}    Missing: {hyperlink}'
						message += Style.RESET_ALL
						print(message) 
					continue 
				
			queue.insert(hyperlink) 
			if verbose: print('    Added:', hyperlink)
			
			if queue.is_full(): 
				return 
		elif verbose: #and hyperlink is not None and \
			    #len(hyperlink) > 0 and hyperlink[0] != '#':
			# This is more of a debugging utility; "None" and "#" hyperlinks
			# don't really provide much information
			print(Fore.YELLOW + '    Invalid:', hyperlink, Style.RESET_ALL) 


# Prints the usage of this file to stderr 
def print_usage(): 
	lines = [\
		'Usage: ',                                                             \
		'    python3 crawl.py <start> <limit> [-o <output>]',                  \
		'        [-t <timeout>] [--verbose] [--validate]',                     \
		'',                                                                    \
		'Options:',                                                            \
		'    <start>: Starting hyperlink (string)',                            \
		'    <limit>: How many links to search for (positive integer)',        \
		'    <output>: Optional, where to put the resulting collection of ',   \
		'        links (file, string), default is stdout',                     \
		'    <timeout>: Optional, how long to wait for a web response from a ',\
		'        given hyperlink before moving on, default is 5 seconds',      \
		'    verbose: If supplied, prints debug information to stdout',        \
		'    validate: If supplied, attempts to ping each hyperlink found to ',\
		'        verify it actually exists']
		
	for line in lines: 
		eprint(line, do_color=False) 


def main(args):
	# For ease of testing, this turns command-line arguments passed as a string
	# into something more traditionally used with sys.argv
	if isinstance(args, str): 
		args = re.findall(r'("[^"]+"|[^\s"]+)', args) 
	
	if len(args) < 3: 
		eprint(f'Error: expected at least 2 arguments, found {len(args)-1}\n')  
		print_usage() 
		sys.exit(1) 
		
	start = args[1] 
	
	# Parses limit (must be a positive integer) 
	try:
		limit = int(args[2]) 
	except ValueError:
		eprint('Error: limit must be an integer\n')
		print_usage()
		sys.exit(1) 
	
	if limit <= 0:
		eprint('Error: limit must be positive\n') 
		print_usage() 
		sys.exit(1) 
	
	output_file_directory = None
	verbose = None 
	timeout = None 
	validate = None 
	try: 
		short = 'o:v:t:verb:val' 
		long = ['verbose', 'validate']
		iterator = getopt.gnu_getopt(args, short, long)[0]
	except getopt.GetoptError as ex:
		eprint(f'Error: unrecognized argument specified "{ex.opt}"\n')
		print_usage() 
		sys.exit(1) 
	for option, value in iterator:
		if option == '-o':
			if output_file_directory is not None: 
				eprint('Error: only one argument can specify an output file\n')
				print_usage() 
				sys.exit(1) 
		
			# Determines where to put output 
			output_file_directory = os.getcwd() + os.sep + value
			
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
				
		elif option == '--validate':
			validate = True 
			
		else: 
			eprint(f'Error: unrecognized argument specified "{ex.opt}"\n')
			print_usage() 
			sys.exit(1) 
			
	# Default values 
	if verbose is None: verbose = False 
	if timeout is None:   timeout = 5
	if validate is None:  validate = False 
	
	# Open either a new file or stdout 
	if output_file_directory is None: 
		output_file = sys.stdout 
	else: 
		if verbose: print(f'Opening {output_file_directory} ... ', end='') 
		
		try: 
			output_file = open(output_file_directory, 'w')
		except OSError: 
			message =  'Error: cannot open output file "'
			message += output_file_directory + '"\n' 
			eprint(message)
			sys.exit(1)
			
		if verbose: print(Fore.CYAN + 'done' + Style.RESET_ALL) 
	
	# Process each website in a breadth-first search starting with the start 
	# hyperlink. 
	queue = CircularQueue(limit) 
	queue.insert(start) 
	while not queue.is_full() and not queue.is_limit(): 
		process_website(queue, verbose, timeout, validate)
	
	# Print the contents of the queue to the output file 
	if verbose and output_file != sys.stdout: 
		print(f'Writing to {output_file_directory} ... ', end='') 
	
	for hyperlink in queue: 
		output_file.write(hyperlink + '\n') 
	
	if output_file != sys.stdout:
		output_file.close() 
		if verbose: print(Fore.CYAN + 'done' + Style.RESET_ALL) 


# Boilerplate tests that verify command-line arguments, where the key is the
# name of the test and the value is the arguments supplied.
cla_tests = {                                                                  \
'no_args':                                                                     \
	'crawl.py',                                                                \
'limit_not_numeric':                                                           \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science limit',           \
'limit_negative':                                                              \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science -10',             \
'output_directory_unknown':                                                    \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 ' +            \
	'-o /some/nonexistant/directory/file.out',                                 \
'timeout_not_numeric':                                                         \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 -t timeout',   \
'timeout_negative':                                                            \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 -t -3.14',     \
'unknown_option':                                                              \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 -q',           \
'verbose_misspelled':                                                          \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 ' +            \
	'--verboseoutput',                                                         \
'validate_misspelled':                                                         \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 --validation', \
'multiple_output_specified':                                                   \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 ' +            \
	'-o file1.out -o file2.out',                                               \
'multiple_timeout_specified':                                                  \
	'crawl.py https://en.wikipedia.org/wiki/Computer_science 10 -t 5 -t 10'    \
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
	# Test that websites will correctly timeout and continue searching after
	def test_timeout(self):
		args = 'crawl.py https://crouton.net 10 -t 0.0001 --verbose'
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(args)
			self.assertRegex(fake_out.getvalue(), r'timed out')
	
	
	# Tests that the program won't crash if it can't find enough websites to 
	# completely meet the limit 
	def test_not_enough_links(self): 
		args = 'crawl.py https://crouton.net/ 10 --verbose'
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(args)
			# The output should not indicate that more than one link was added
			# to the queue. 
			self.assertNotRegex(fake_out.getvalue(), r'Added:')
	
	
	# Tests that validation works. The given website contains links which do not
	# lead anywhere, so they should not be added to the queue. 
	def test_validate(self): 
		args =  'crawl.py https://www.cs.rice.edu/CS/compilers/ 3 -t 10 ' 
		args += '--verbose --validate' 
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out:
			main(args)
			# The output should indicate that some of the links do not work
			# after being pinged
			self.assertRegex(fake_out.getvalue(), r'Missing:')
			
	
	# Tests that the final output does not contain repeated entries
	def test_repeat(self): 
		args = 'crawl.py https://en.wikipedia.org/wiki/Computer_science 250' 
		with unittest.mock.patch('sys.stdout', new = io.StringIO()) as fake_out: 
			main(args)
			# The output collection is stored as a line-separated list of 
			# strings, so this ensures that the list contains only unique values
			links = fake_out.getvalue().split('\n')
			self.assertEqual(len(links), len(set(links))) 
			

if __name__ == '__main__':
	main(sys.argv)