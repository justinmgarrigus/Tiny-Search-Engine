import requests, json
import csv

def prepSuggestionMaster():
  headers = {
      "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582"
  }
  suggestionSeeds = open("/data/suggestionSeeds.txt").read().splitlines()
  fout = open('/data/suggestionMaster.csv', 'w')
  suggestionCSVWriter = csv.writer(fout)

  for seed in suggestionSeeds:
    rowToWrite = []
    response = requests.get('http://google.com/complete/search?client=chrome&q=' + seed, headers=headers)
    for result in json.loads(response.text)[1]:
      rowToWrite.append(result)
    suggestionCSVWriter.writerow(rowToWrite)

 
