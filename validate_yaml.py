import yaml
import sys

files = ["Iteration 3.yaml", "Singularity_Dave_Brain.QTL"]

for f in files:
    try:
        with open(f, 'r') as stream:
            yaml.safe_load(stream)
        print(f"✅ {f}: Valid YAML")
    except Exception as e:
        print(f"❌ {f}: Invalid YAML - {e}")
        sys.exit(1)
