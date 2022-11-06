
_MAX_SUGGESTIONS = 5
# use instantiatedobject.insert(single string) to insert a single search suggestion option
# use instantiaedobject.batch_insert([list]) to insert more than one search suggestion option
# both of those above should not be accessed during runtime, all new search suggestions should be appended to suggestionSeeds.txt TODO
# instantiatedobject.search(string) returns a list of search suggestion options based on the passed string
# Create an object in the driver program and initialize it with the CSV suggestions:
"""
ss = SearchSuggestion()
with open('/data/suggestionMaster.csv') as file_obj:
      
      reader_obj = csv.reader(file_obj)
      
      for row in reader_obj:
        ss.batch_insert(row)
"""

class _Node:
    def __init__(self, data):
      
        self.data = data    #phrase or suggestion
        self.end_of_word = False #Flag to signify end of a phrase or word (i.e. search termination flag)
        self.child = {}     #empty connection to child node


class SearchSuggestion:
    def __init__(self):
        self.root = _Node(None)     #initializing root node of trie
        self.count = 0              #count set at zero

    def get_count(self) -> int:
        #returns the total number of words in Trie
        return self.count

    def insert(self, word: str) -> None:

        word = word.strip()                                 #stripping string to preprocess for insertion
        curr = self.root                                    #beggining at root
        while word:                                         #through end of word
            if word[0] not in curr.child:                   #check first prefix to see if applicable child exists
                curr.child[word[0]] = _Node(word[0])        #if it doesn't exist, make a child of that prefix
            curr = curr.child[word[0]]                      #make current prefix the first prefix of the current word
            word = word[1:]                                 #stem catalogued prefix from word, and recurr
            if len(word) == 0 and not curr.end_of_word:     #Once the end of the word is found (word stemmed to nothing), flag end of word as true,
                curr.end_of_word = True                     #and increment word count.
                self.count += 1

    def batch_insert(self, words: [str]) -> None:           #given a list, iteratively call the insert function
        for word in words:
            self.insert(word)

    def search(self, word: str, max_suggestions=_MAX_SUGGESTIONS) -> [str]:               #searches are similar to insertions with different flag behavior
                                                                                          #Given a word, and a number of desired suggestions, (default 5),
                                                                                          #the function returns a list of suggestions 
        result = []                                      #temp array
        curr = self.root                                 #starting at root
        word = word.strip()                              #stripping word for preprocessing

        if not word:                                     #return null if nothing passed
            return result

        og_word = word                                   #deep copy of word to preserve original

        while word:
            if word[0] not in curr.child:                #search found nothing
                return result
            curr = curr.child[word[0]]                   #otherwise similar to search in the prefix stemming
            word = word[1:]

        if curr.end_of_word:                             #once end of phrase found, add suggestion to list of suggestions
            result.append(og_word)

        def _search_helper(self, word: str, node: _Node) -> [str]:      #helper traversal function
            if len(result) >= max_suggestions:                          #stop traversing if max number of suggestions is met
                return result
            for child_node in node.child.values():                            #looking through each child value
                if child_node.end_of_word and len(result) < max_suggestions:  #appending if end of phrase (suggestion met)
                    result.append(word + child_node.data)
                _search_helper(self, word + child_node.data, child_node)      #recurr with result
            return result
        return _search_helper(self, og_word, curr)
