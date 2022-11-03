import sys 
from colorama import Fore, Style 


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