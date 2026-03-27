#!/usr/bin/env python3
import yaml
import os
import json

packs_dir = "packs"
files = sorted(os.listdir(packs_dir))

results = []
for f in files:
    if f.endswith('.yaml'):
        path = os.path.join(packs_dir, f)
        with open(path) as fp:
            data = yaml.safe_load(fp)
        
        name = data.get('id', '').split('/')[-1]
        confidence = data.get('confidence', 'inferred')
        tier = data.get('tier', 'COMMUNITY')
        problem_class = data.get('problem_class', '')
        phase_count = len(data.get('phases', [])) if 'phases' in data else 0
        domain = data.get('domain', '')
        
        results.append({
            'file': f,
            'name': name,
            'confidence': confidence,
            'tier': tier,
            'problem_class': problem_class,
            'phase_count': phase_count,
            'domain': domain
        })
        
print(json.dumps(results, indent=2))