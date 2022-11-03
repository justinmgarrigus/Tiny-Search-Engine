
_MAX_SUGGESTIONS = 10
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
        """Node class used to store words in trie
        Args:
            data (str): word to save
        """
        self.data = data    #phrase or suggestion
        self.end_of_word = False
        self.child = {}     #empty connection to child node


class SearchSuggestion:
    def __init__(self):
        self.root = _Node(None)     #initializing root node of trie
        self.count = 0

    def get_count(self) -> int:
        #returns the total number of words in Trie
        return self.count

    def insert(self, word: str) -> None:

        word = word.strip()   
        curr = self.root
        while word:
            if word[0] not in curr.child:
                curr.child[word[0]] = _Node(word[0])
            curr = curr.child[word[0]]
            word = word[1:]
            if len(word) == 0 and not curr.end_of_word:
                curr.end_of_word = True
                self.count += 1

    def batch_insert(self, words: [str]) -> None:
        """Given a list of words will be stored in trie data structure
        Args:
            words ([str]): List of words to store
        """
        for word in words:
            self.insert(word)

    def search(self, word: str, max_suggestions=_MAX_SUGGESTIONS) -> [str]:
        """Given a prefix, will search for words starting with the prefix
        Args:
            word (str): Prefix to search by.
            max_suggestions (int, optional): Number of suggestions in the result. Defaults to 10.
        Returns:
            [str]: List of words with the given prefix
        """
        result = []
        curr = self.root
        word = word.strip()

        if not word:
            return result

        og_word = word

        while word:
            if word[0] not in curr.child:
                return result
            curr = curr.child[word[0]]
            word = word[1:]

        if curr.end_of_word:
            result.append(og_word)

        def _search_helper(self, word: str, node: _Node) -> [str]:
            """Recursive function to search trie
            Args:
                word (str): Current word
                node (_Node): Current node
            Returns:
                [str]: List of words with the given prefix
            """
            if len(result) >= max_suggestions:
                return result
            for child_node in node.child.values():
                if child_node.end_of_word and len(result) < max_suggestions:
                    result.append(word + child_node.data)
                _search_helper(self, word + child_node.data, child_node)
            return result
        return _search_helper(self, og_word, curr)