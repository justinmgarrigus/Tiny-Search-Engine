import requests, json
import csv

def prepSuggestionMaster():
  #requesting access to a browser using the requests api
  headers = {
      "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582"
  }
  suggestionSeeds = open("/data/suggestionSeeds.txt").read().splitlines()   #opening and reading the suggestion seeds
  fout = open('/data/suggestionMaster.csv', 'w')                            #openning the master suggestion csv
  suggestionCSVWriter = csv.writer(fout)    #prepping the csv writer

  #iterating through each suggestion seed
  for seed in suggestionSeeds:
    rowToWrite = []             #temporary array
    response = requests.get('http://google.com/complete/search?client=chrome&q=' + seed, headers=headers)   #searching to elaborate seed
    for result in json.loads(response.text)[1]:                                                             #grabbing json file of results
      rowToWrite.append(result)                                                                             #appending to temporary row
    suggestionCSVWriter.writerow(rowToWrite)                                                                #writing everything to the master CSV

 
