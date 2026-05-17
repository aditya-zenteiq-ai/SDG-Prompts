import os
import json
import sys

sys.path.insert(0, "/home/sushmetha/sushmetha/synthetic_dataset/cooking/scripts")
from persona_bundles import GLOBAL_DIETARY, AUDIENCE_POOL, SERVING_SCALES, LANG_OUT, COMPATIBILITY, PRESERVATION_BY_REGION, ALL_REGIONS

rotations = {
    "metadata": {
        "description": "These are the rotation variables used to augment and diversify the synthetic dataset generation. When a prompt uses variables like dietary restrictions, audiences, or regions, they should be drawn from these lists.",
        "source": "persona_bundles.py"
    },
    "global_variables": {
        "dietary_restrictions": GLOBAL_DIETARY,
        "audiences": AUDIENCE_POOL,
        "serving_scales": [{"from": s[0], "to": s[1]} for s in SERVING_SCALES],
        "languages_out": LANG_OUT,
        "regions": ALL_REGIONS
    },
    "regional_variables": {
        "festivals_by_region": {r: COMPATIBILITY[r]["festivals"] for r in ALL_REGIONS if r in COMPATIBILITY},
        "preservation_methods_by_region": {r: PRESERVATION_BY_REGION.get(r, []) for r in ALL_REGIONS}
    }
}

folders = [
    "/home/sushmetha/SDG-Prompts/Mid-Training/Domain-Specific/Cooking",
    "/home/sushmetha/SDG-Prompts/Mid-Training/Domain-Specific/Household",
    "/home/sushmetha/SDG-Prompts/Mid-Training/General",
    "/home/sushmetha/SDG-Prompts/Mid-Training/General/Dense_CoT",
    "/home/sushmetha/SDG-Prompts/Mid-Training/General/Dense_QA",
    "/home/sushmetha/SDG-Prompts/Mid-Training/General/Reconstruction",
    "/home/sushmetha/SDG-Prompts/Mid-Training/General/Rephrasing",
    "/home/sushmetha/SDG-Prompts/Mid-Training/General/Structured_Extraction",
    "/home/sushmetha/SDG-Prompts/SFT/Domain-Specific/Cooking",
    "/home/sushmetha/SDG-Prompts/SFT/Domain-Specific/First_Aid",
    "/home/sushmetha/SDG-Prompts/SFT/Domain-Specific/Household"
]

for base_dir in folders:
    rot_dir = os.path.join(base_dir, "Rotation Conditions")
    os.makedirs(rot_dir, exist_ok=True)
    
    file_path = os.path.join(rot_dir, "cooking_rotation_variables.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(rotations, f, indent=4)
        
print("Rotations distributed!")
