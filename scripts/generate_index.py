#!/usr/bin/env python3
import yaml
import os
import json
from datetime import datetime

packs_dir = "packs"
files = sorted(os.listdir(packs_dir))

packs = []
for f in files:
    if f.endswith('.yaml'):
        path = os.path.join(packs_dir, f)
        with open(path) as fp:
            data = yaml.safe_load(fp)
        
        name = data.get('id', '').split('/')[-1]
        pack_type = data.get('type', 'workflow_pack')
        
        entry = {
            "id": data.get('id', ''),
            "name": name,
            "type": pack_type,
            "problem_class": data.get('problem_class', ''),
            "confidence": data.get('confidence', 'inferred'),
            "tier": data.get('tier', 'COMMUNITY'),
            "phase_count": len(data.get('phases', [])) if 'phases' in data else 0,
            "version": data.get('version', '1.0.0')
        }
        
        if pack_type == 'critique_rubric':
            entry["domain"] = data.get('domain', 'software-development')
            entry["criteria_count"] = len(data.get('criteria', [])) if 'criteria' in data else 0
        elif 'phases' in data and data['phases']:
            entry["phase_names"] = [p.get('name', '') for p in data['phases']]
        
        if data.get('mental_model'):
            entry["mental_model"] = data.get('mental_model')
        
        packs.append(entry)

index = {
    "packs": packs,
    "feedback": [],
    "examples": [],
    "updated": datetime.utcnow().isoformat() + "+00:00"
}

print(json.dumps(index, indent=2))