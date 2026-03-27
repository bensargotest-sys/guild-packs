import json
d = json.load(open('index_new.json'))
print(f"Packs count: {len(d['packs'])}")