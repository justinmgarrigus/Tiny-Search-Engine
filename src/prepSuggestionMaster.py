import requests, json  #required in driver
import csv             #required

_MAX_RESPONSES = 5   #same as search suggestions file

def appendPrepSuggestionMaster(): #this should be used in most cases for initialization
  #requesting access to a browser using the requests api
  headers = { #include this
      "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582"
  }

  suggestionSeeds = open("/content/suggestionSeeds.txt").read().splitlines()   #opening and reading the suggestion seeds
  cachedPlace = open("/content/lastSeed.txt").read().splitlines()
  print(cachedPlace[0])
  appendSuggestions = []
  i = len(suggestionSeeds) - 1
  k = int(cachedPlace[1])
  cacheLine = str(i)
  tempItem = suggestionSeeds[i]
  if k != i:
      f = open('/content/lastSeed.txt', 'w')
      f.write(tempItem + "\n")
      a = open('/content/lastSeed.txt', 'a')
      a.writelines(cacheLine)
      while i >= k:
        tempItem = suggestionSeeds[i]
        appendSuggestions.append(tempItem)
        i = i - 1

  fout = open('/content/suggestionMaster.csv', 'a', newline="")                            #openning the master suggestion csv
  suggestionCSVWriter = csv.writer(fout)    #prepping the csv writer
  print(appendSuggestions)
  print("\n")
  #iterating through each suggestion seed
  if len(appendSuggestions) != 0:
    for seed in appendSuggestions: 
      response = requests.get('http://google.com/complete/search?client=chrome&q=' + seed, headers=headers)   #searching to elaborate seed                                #appending to temporary row
      print(json.loads(response.text)[1])
      suggestionCSVWriter.writerow(json.loads(response.text)[1])

def resetPrepSuggestionMaster():
  #requesting access to a browser using the requests api
  headers = { #include this
      "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582"
  }
  suggestionSeeds = open("/content/suggestionSeeds.txt").read().splitlines()   #opening and reading the suggestion seeds
  fout = open('/content/suggestionMaster.csv', 'w')                            #openning the master suggestion csv
  suggestionCSVWriter = csv.writer(fout)    #prepping the csv writer

  #iterating through each suggestion seed
  for seed in suggestionSeeds: 
    response = requests.get('http://google.com/complete/search?client=chrome&q=' + seed, headers=headers)   #searching to elaborate seed                                #appending to temporary row
    suggestionCSVWriter.writerow(json.loads(response.text)[1])

def searchSuggestionDriver(partialSearch): #pass the string without the suffix '?'
  normalizedSearch = partialSearch.lower() #changing all seeds to lowercase
  suggestions = ss.search(normalizedSearch) #searching for suggestions to the given search
  seedout = open('/content/suggestionSeeds.txt', 'a') #adding the last seach to the seed list to grow functionality
  seedout.write("\n" + normalizedSearch) 
  if len(suggestions) == 0: #if no suggestions are given, make some in real time
    headers = { 
      "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582"
    }
    response = requests.get('http://google.com/complete/search?client=chrome&q=' + normalizedSearch, headers=headers)   #searching to elaborate seed
    unseenSuggestions = json.loads(response.text)[1]

    return unseenSuggestions[:_MAX_RESPONSES]
  
  return suggestions[:_MAX_RESPONSES]
